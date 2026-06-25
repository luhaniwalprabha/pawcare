# Billing endpoint handles invoice creation and payment tracking.
#
# Key design decisions:
#
# 1. Invoice number generation:
#    Format: PAW-YYYYMMDD-{id padded to 4 digits}
#    e.g. PAW-20260101-0042
#    Simple, readable, traceable to date.
#    In production you'd use a sequence or UUID for uniqueness guarantees.
#
# 2. Tax calculation:
#    Hardcoded at 18% GST for India.
#    In production this would come from a config or tax service.
#
# 3. Line item totals:
#    Calculated server-side (quantity * unit_price).
#    Never trust the client to send pre-calculated totals.
#
# 4. Payment marking:
#    Separate endpoint PATCH /{id}/pay — clean single responsibility.
#    Sets paid_at timestamp and changes status to PAID atomically.
#
# 5. Role restriction:
#    Creating/updating invoices: receptionist, admin
#    Marking paid: receptionist, admin
#    Viewing: any authenticated user (vet needs to see billing too)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, date
from app.db.session import get_db
from app.models.clinic import Invoice, InvoiceLineItem, InvoiceStatus, Appointment
from app.schemas.billing import InvoiceCreate, InvoiceUpdate, InvoiceOut
from app.core.security import get_current_user, require_roles

router = APIRouter()

TAX_RATE = 0.18  # 18% GST


def generate_invoice_number(invoice_id: int) -> str:
    today = datetime.utcnow().strftime("%Y%m%d")
    return f"PAW-{today}-{str(invoice_id).zfill(4)}"


def get_invoice_or_404(invoice_id: int, db: Session) -> Invoice:
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("", response_model=List[InvoiceOut])
def list_invoices(
    status: InvoiceStatus = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Invoice).options(joinedload(Invoice.line_items))
    if status:
        q = q.filter(Invoice.status == status)
    return q.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin", "receptionist")),
):
    # Validate appointment exists
    appointment = db.query(Appointment).filter(
        Appointment.id == payload.appointment_id
    ).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Prevent duplicate invoices for same appointment
    existing = db.query(Invoice).filter(
        Invoice.appointment_id == payload.appointment_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Invoice already exists for this appointment")

    if not payload.line_items:
        raise HTTPException(status_code=400, detail="Invoice must have at least one line item")

    # Calculate totals server-side — never trust client calculations
    subtotal = sum(item.quantity * item.unit_price for item in payload.line_items)
    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax, 2)

    # Create invoice
    invoice = Invoice(
        appointment_id=payload.appointment_id,
        invoice_number="PENDING",  # will update after we have the ID
        status=InvoiceStatus.DRAFT,
        subtotal=round(subtotal, 2),
        tax=tax,
        total=total,
        due_date=payload.due_date,
        notes=payload.notes,
    )
    db.add(invoice)
    db.flush()  # flush to get the invoice ID without committing

    # Now set the invoice number using the generated ID
    invoice.invoice_number = generate_invoice_number(invoice.id)

    # Create line items
    for item in payload.line_items:
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total=round(item.quantity * item.unit_price, 2),
        )
        db.add(line_item)

    db.commit()
    db.refresh(invoice)
    return get_invoice_or_404(invoice.id, db)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return get_invoice_or_404(invoice_id, db)


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin", "receptionist")),
):
    invoice = get_invoice_or_404(invoice_id, db)
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Cannot update a paid invoice")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    db.commit()
    db.refresh(invoice)
    return get_invoice_or_404(invoice_id, db)


@router.patch("/{invoice_id}/pay", response_model=InvoiceOut)
def mark_invoice_paid(
    invoice_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin", "receptionist")),
):
    """
    Mark invoice as paid.
    Sets paid_at timestamp atomically with status change.
    Separate endpoint keeps responsibility clear — paying is different from editing.
    """
    invoice = get_invoice_or_404(invoice_id, db)
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot pay a cancelled invoice")
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)
    return get_invoice_or_404(invoice_id, db)


@router.delete("/{invoice_id}", status_code=204)
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    invoice = get_invoice_or_404(invoice_id, db)
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Cannot cancel a paid invoice")
    invoice.status = InvoiceStatus.CANCELLED
    db.commit()