from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.db.session import get_db
from app.models.clinic import MedicalRecord, Appointment, AppointmentStatus
from app.models.patient import Pet
from app.schemas.clinic import MedicalRecordCreate, MedicalRecordUpdate, MedicalRecordOut
from app.core.security import get_current_user, require_roles

router = APIRouter()


def get_record_or_404(record_id: int, db: Session) -> MedicalRecord:
    record = (
        db.query(MedicalRecord)
        .options(joinedload(MedicalRecord.vet), joinedload(MedicalRecord.pet))
        .filter(MedicalRecord.id == record_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
    return record


@router.get("/pet/{pet_id}", response_model=List[MedicalRecordOut])
def get_pet_medical_history(
    pet_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if not db.query(Pet).filter(Pet.id == pet_id).first():
        raise HTTPException(status_code=404, detail="Pet not found")
    return (
        db.query(MedicalRecord)
        .options(joinedload(MedicalRecord.vet))
        .filter(MedicalRecord.pet_id == pet_id)
        .order_by(MedicalRecord.visit_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("", response_model=MedicalRecordOut, status_code=201)
def create_medical_record(
    payload: MedicalRecordCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("vet", "admin")),
):
    # Validate pet exists
    if not db.query(Pet).filter(Pet.id == payload.pet_id).first():
        raise HTTPException(status_code=404, detail="Pet not found")

    # If linked to appointment, validate and mark as completed
    if payload.appointment_id:
        appointment = db.query(Appointment).filter(
            Appointment.id == payload.appointment_id
        ).first()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.pet_id != payload.pet_id:
            raise HTTPException(status_code=400, detail="Appointment does not belong to this pet")
        if appointment.medical_record:
            raise HTTPException(status_code=409, detail="Medical record already exists for this appointment")
        # Auto-complete the appointment
        appointment.status = AppointmentStatus.COMPLETED

    record = MedicalRecord(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return get_record_or_404(record.id, db)


@router.get("/{record_id}", response_model=MedicalRecordOut)
def get_medical_record(
    record_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return get_record_or_404(record_id, db)


@router.patch("/{record_id}", response_model=MedicalRecordOut)
def update_medical_record(
    record_id: int,
    payload: MedicalRecordUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("vet", "admin")),
):
    record = get_record_or_404(record_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return get_record_or_404(record_id, db)


@router.delete("/{record_id}", status_code=204)
def delete_medical_record(
    record_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    record = get_record_or_404(record_id, db)
    db.delete(record)
    db.commit()