import os
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from time import perf_counter
from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlmodel import Field, Session, SQLModel, create_engine, select


class InvoiceStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class InvoiceCreate(SQLModel):
    customer_id: int = Field(gt=0, description="Identifier of the customer being billed")
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, description="Invoice amount")
    currency: str = Field(min_length=3, max_length=3, description="Three-letter ISO-style currency code")


class Invoice(InvoiceCreate, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: InvoiceStatus = Field(default=InvoiceStatus.PENDING, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class InvoiceRead(InvoiceCreate):
    id: int
    status: InvoiceStatus
    created_at: datetime


DATABASE_URL = os.getenv("BILLING_API_DATABASE_URL", "sqlite:///./billing.db")

http_requests_total = Counter(
    "billing_api_http_requests_total",
    "Total HTTP requests handled by the Billing API",
    ("method", "path", "status"),
)
http_request_duration_seconds = Histogram(
    "billing_api_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path"),
)
invoices_created_total = Counter("billing_api_invoices_created_total", "Total invoices created")
invoices_paid_total = Counter("billing_api_invoices_paid_total", "Total invoices marked as paid")


def _metric_path(path: str) -> str:
    if path.startswith("/invoices/"):
        suffix = path.removeprefix("/invoices/")
        if suffix.split("/", 1)[0].isdigit():
            return "/invoices/{invoice_id}" + ("/" + suffix.split("/", 1)[1] if "/" in suffix else "")
    return path


class MetricsMiddleware:
    def __init__(self, application: Any):
        self.application = application

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.application(scope, receive, send)
            return
        started = perf_counter()
        response_status = 500

        async def record_response(message: dict[str, Any]) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        await self.application(scope, receive, record_response)
        path = _metric_path(scope.get("path", "unknown"))
        http_requests_total.labels(scope["method"], path, str(response_status)).inc()
        http_request_duration_seconds.labels(scope["method"], path).observe(perf_counter() - started)


def create_app(database_url: str = DATABASE_URL, enable_metrics: bool = True) -> FastAPI:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)

    application = FastAPI(
        title="SparrowX Labs Billing API",
        description="Manages customer invoices and payment status for the Finance Platform team. Owned by Sophie Wilson.",
        version="1.0.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8080,http://localhost:3000").split(","),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.engine = engine
    if enable_metrics:
        application.add_middleware(MetricsMiddleware)

    async def get_session(request: Request) -> AsyncGenerator[Session, None]:
        with Session(request.app.state.engine) as session:
            yield session

    SessionDependency = Annotated[Session, Depends(get_session)]

    @application.get("/health", tags=["system"], summary="Health check")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/metrics", tags=["system"], summary="Prometheus metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.post(
        "/invoices",
        response_model=InvoiceRead,
        status_code=status.HTTP_201_CREATED,
        tags=["invoices"],
        summary="Create an invoice",
    )
    async def create_invoice(payload: InvoiceCreate, session: SessionDependency) -> Invoice:
        normalized = payload.model_copy(update={"currency": payload.currency.upper()})
        invoice = Invoice.model_validate(normalized)
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        invoices_created_total.inc()
        return invoice

    @application.get("/invoices", response_model=list[InvoiceRead], tags=["invoices"], summary="List invoices")
    async def list_invoices(
        session: SessionDependency,
        invoice_status: InvoiceStatus | None = Query(default=None, alias="status", description="Filter by invoice status"),
        offset: int = Query(default=0, ge=0, description="Number of invoices to skip"),
        limit: int = Query(default=100, ge=1, le=100, description="Maximum invoices to return"),
    ) -> list[Invoice]:
        statement = select(Invoice)
        if invoice_status is not None:
            statement = statement.where(Invoice.status == invoice_status)
        statement = statement.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
        return list(session.exec(statement).all())

    @application.get(
        "/invoices/{invoice_id}",
        response_model=InvoiceRead,
        tags=["invoices"],
        summary="Retrieve an invoice",
        responses={404: {"description": "Invoice not found"}},
    )
    async def get_invoice(invoice_id: int, session: SessionDependency) -> Invoice:
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice

    @application.post(
        "/invoices/{invoice_id}/pay",
        response_model=InvoiceRead,
        tags=["invoices"],
        summary="Mark an invoice as paid",
        responses={404: {"description": "Invoice not found"}, 409: {"description": "Invoice cannot be paid in its current state"}},
    )
    async def pay_invoice(invoice_id: int, session: SessionDependency) -> Invoice:
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.status is not InvoiceStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only pending invoices can be paid")
        invoice.status = InvoiceStatus.PAID
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        invoices_paid_total.inc()
        return invoice

    @application.post(
        "/invoices/{invoice_id}/cancel",
        response_model=InvoiceRead,
        tags=["invoices"],
        summary="Cancel an invoice",
        responses={404: {"description": "Invoice not found"}, 409: {"description": "Invoice cannot be cancelled in its current state"}},
    )
    async def cancel_invoice(invoice_id: int, session: SessionDependency) -> Invoice:
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.status is not InvoiceStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only pending invoices can be cancelled")
        invoice.status = InvoiceStatus.CANCELLED
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        return invoice

    return application


app = create_app()
