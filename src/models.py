from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel


class InvoiceStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class InvoiceFields(SQLModel):
    customer_id: int = Field(gt=0, description="Identifier of the customer being billed")
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, description="Invoice amount")
    currency: str = Field(min_length=3, max_length=3, description="Three-letter ISO-style currency code")


class Invoice(InvoiceFields, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: InvoiceStatus = Field(default=InvoiceStatus.PENDING, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
