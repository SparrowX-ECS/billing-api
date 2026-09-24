from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session, select

from src.models import Invoice, InvoiceStatus
from src.schemas import InvoiceCreate, InvoiceRead


router = APIRouter(prefix="/api/billing", tags=["invoices"])


def get_session(request: Request) -> Generator[Session, None, None]:
    with Session(request.app.state.engine) as session:
        yield session


@router.post("/", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate, session: Session = Depends(get_session)) -> Invoice:
    normalized = payload.model_copy(update={"currency": payload.currency.upper()})
    invoice = Invoice.model_validate(normalized)
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


@router.get("/", response_model=list[InvoiceRead])
def list_invoices(
    session: Session = Depends(get_session),
    invoice_status: InvoiceStatus | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[Invoice]:
    statement = select(Invoice)
    if invoice_status is not None:
        statement = statement.where(Invoice.status == invoice_status)
    statement = statement.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
    return list(session.exec(statement).all())


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def update_invoice_status(invoice_id: int, new_status: InvoiceStatus, session: Session) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status is not InvoiceStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only pending invoices can be updated")
    invoice.status = new_status
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/pay", response_model=InvoiceRead)
def pay_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Invoice:
    return update_invoice_status(invoice_id, InvoiceStatus.PAID, session)


@router.post("/{invoice_id}/cancel", response_model=InvoiceRead)
def cancel_invoice(invoice_id: int, session: Session = Depends(get_session)) -> Invoice:
    return update_invoice_status(invoice_id, InvoiceStatus.CANCELLED, session)
