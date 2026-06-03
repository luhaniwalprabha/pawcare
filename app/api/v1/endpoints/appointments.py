from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from app.db.session import get_db
from app.models.clinic import Appointment, AppointmentStatus
from app.models.patient import Pet
from app.models.user import User
from app.schemas.clinic import (
    AppointmentCreate, AppointmentUpdate,
    AppointmentStatusUpdate, AppointmentOut
)
from app.core.security import get_current_user, require_roles

router = APIRouter()


def get_appointment_or_404(appointment_id: int, db: Session) -> Appointment:
    appointment = (
        db.query(Appointment)
        .options(joinedload(Appointment.pet), joinedload(Appointment.vet))
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.get("", response_model=List[AppointmentOut])
def list_appointments(
    pet_id: Optional[int] = None,
    vet_id: Optional[int] = None,
    status: Optional[AppointmentStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Appointment).options(
        joinedload(Appointment.pet),
        joinedload(Appointment.vet)
    )
    if pet_id:
        q = q.filter(Appointment.pet_id == pet_id)
    if vet_id:
        q = q.filter(Appointment.vet_id == vet_id)
    if status:
        q = q.filter(Appointment.status == status)
    if date_from:
        q = q.filter(Appointment.scheduled_at >= date_from)
    if date_to:
        q = q.filter(Appointment.scheduled_at <= date_to)
    return q.order_by(Appointment.scheduled_at).offset(skip).limit(limit).all()


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Validate pet exists
    if not db.query(Pet).filter(Pet.id == payload.pet_id).first():
        raise HTTPException(status_code=404, detail="Pet not found")

    # Validate vet exists and has vet role
    if payload.vet_id:
        vet = db.query(User).filter(User.id == payload.vet_id).first()
        if not vet:
            raise HTTPException(status_code=404, detail="Vet not found")
        if vet.role not in ("vet", "admin"):
            raise HTTPException(status_code=400, detail="Assigned user is not a vet")

    # Check for conflicting appointments for the same vet
    if payload.vet_id:
        conflict = db.query(Appointment).filter(
            Appointment.vet_id == payload.vet_id,
            Appointment.scheduled_at == payload.scheduled_at,
            Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Vet already has an appointment at this time")

    appointment = Appointment(**payload.model_dump())
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return get_appointment_or_404(appointment.id, db)


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return get_appointment_or_404(appointment_id, db)


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    appointment = get_appointment_or_404(appointment_id, db)
    if appointment.status == AppointmentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot update a completed appointment")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(appointment, field, value)
    db.commit()
    db.refresh(appointment)
    return get_appointment_or_404(appointment_id, db)


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
def update_appointment_status(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    appointment = get_appointment_or_404(appointment_id, db)

    # Enforce valid status transitions
    valid_transitions = {
        AppointmentStatus.SCHEDULED: [AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
        AppointmentStatus.CONFIRMED: [AppointmentStatus.IN_PROGRESS, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
        AppointmentStatus.IN_PROGRESS: [AppointmentStatus.COMPLETED],
        AppointmentStatus.COMPLETED: [],
        AppointmentStatus.CANCELLED: [],
        AppointmentStatus.NO_SHOW: [],
    }
    if payload.status not in valid_transitions[appointment.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {appointment.status} to {payload.status}"
        )
    appointment.status = payload.status
    db.commit()
    db.refresh(appointment)
    return get_appointment_or_404(appointment_id, db)


@router.delete("/{appointment_id}", status_code=204)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin", "receptionist")),
):
    appointment = get_appointment_or_404(appointment_id, db)
    if appointment.status == AppointmentStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot delete a completed appointment")
    db.delete(appointment)
    db.commit()