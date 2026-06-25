# Pydantic schemas for billing — these define what the API
# accepts as input and returns as output for invoices.
#
# Pattern used: Base → Create → Update → Out
#   Base: shared fields
#   Create: fields needed to create (input)
#   Update: all fields optional (PATCH — only send what changed)
#   Out: what the API returns (includes DB-generated fields like id, created_at)

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from app.models.clinic import InvoiceStatus


class InvoiceLineItemCreate(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float


class InvoiceLineItemOut(InvoiceLineItemCreate):
    id: int
    total: float

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    appointment_id: int
    line_items: List[InvoiceLineItemCreate]
    due_date: Optional[date] = None
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    due_date: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[InvoiceStatus] = None


class InvoiceOut(BaseModel):
    id: int
    appointment_id: Optional[int]
    invoice_number: str
    status: InvoiceStatus
    subtotal: float
    tax: float
    total: float
    due_date: Optional[date]
    paid_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    line_items: List[InvoiceLineItemOut] = []

    class Config:
        from_attributes = True