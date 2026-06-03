from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from app.models.clinic import AppointmentStatus, AppointmentType
from app.schemas.patient import PetOut
from app.schemas.auth import UserOut


class AppointmentBase(BaseModel):
    pet_id: int
    vet_id: Optional[int] = None
    appointment_type: AppointmentType
    scheduled_at: datetime
    duration_minutes: int = 30
    reason: Optional[str] = None
    notes: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentUpdate(BaseModel):
    vet_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    reason: Optional[str] = None
    notes: Optional[str] = None

class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus

class AppointmentOut(AppointmentBase):
    id: int
    status: AppointmentStatus
    created_at: datetime
    pet: PetOut
    vet: Optional[UserOut] = None

    class Config:
        from_attributes = True

class MedicalRecordBase(BaseModel):
    pet_id: int
    vet_id: Optional[int] = None
    appointment_id: Optional[int] = None
    visit_date: datetime
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    prescriptions: Optional[str] = None
    weight_at_visit: Optional[float] = None
    temperature: Optional[float] = None
    notes: Optional[str] = None
    follow_up_required: bool = False
    follow_up_date: Optional[date] = None

class MedicalRecordCreate(MedicalRecordBase):
    pass

class MedicalRecordUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    prescriptions: Optional[str] = None
    weight_at_visit: Optional[float] = None
    temperature: Optional[float] = None
    notes: Optional[str] = None
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[date] = None

class MedicalRecordOut(MedicalRecordBase):
    id: int
    ai_summary: Optional[str] = None
    created_at: datetime
    vet: Optional[UserOut] = None

    class Config:
        from_attributes = True