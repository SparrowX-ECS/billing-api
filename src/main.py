import os
import time
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlmodel import SQLModel

from src.database import create_database_engine, database_url_from_environment
from src.models import Invoice  # noqa: F401 - registers the table with SQLModel metadata
from src.routes.invoices import router as invoices_router


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


class MetricsMiddleware:
    def __init__(self, application: Any):
        self.application = application

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.application(scope, receive, send)
            return
        started = time.perf_counter()
        response_status = 500

        async def record_response(message: dict[str, Any]) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        await self.application(scope, receive, record_response)
        http_requests_total.labels(scope["method"], scope.get("path", "unknown"), str(response_status)).inc()
        http_request_duration_seconds.labels(scope["method"], scope.get("path", "unknown")).observe(time.perf_counter() - started)


def create_app(database_url: str | None = None, enable_metrics: bool = True) -> FastAPI:
    application = FastAPI(
        title="SparrowX Labs Billing API",
        description="Manages customer invoices and payment status for the Finance Platform team.",
        version="1.0.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8080,http://localhost:3000").split(","),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.engine = create_database_engine(database_url or database_url_from_environment())
    SQLModel.metadata.create_all(application.state.engine)

    if enable_metrics:
        application.add_middleware(MetricsMiddleware)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/billing/health", tags=["system"])
    def api_health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/metrics", tags=["system"], include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    application.include_router(invoices_router)
    return application


app = create_app()
