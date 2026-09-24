from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from src.models import InvoiceStatus


class InvoiceCreate(SQLModel):
    customer_id: int = Field(gt=0, description="Identifier of the customer being billed")
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, description="Invoice amount")
    currency: str = Field(min_length=3, max_length=3, description="Three-letter ISO-style currency code")


class InvoiceRead(InvoiceCreate):
    id: int
    status: InvoiceStatus
    created_at: datetime
