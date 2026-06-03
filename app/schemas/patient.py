from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
from app.models.patient import Species, Gender


# --- Owner schemas ---

class OwnerBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None


class OwnerCreate(OwnerBase):
    pass


class OwnerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None


class OwnerOut(OwnerBase):
    id: int
    created_at: datetime
    pets: List["PetOut"] = []

    class Config:
        from_attributes = True


# --- Pet schemas ---

class PetBase(BaseModel):
    name: str
    species: Species
    breed: Optional[str] = None
    gender: Gender = Gender.UNKNOWN
    date_of_birth: Optional[date] = None
    weight_kg: Optional[float] = None
    microchip_number: Optional[str] = None
    allergies: Optional[str] = None
    notes: Optional[str] = None


class PetCreate(PetBase):
    owner_id: int


class PetUpdate(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    weight_kg: Optional[float] = None
    microchip_number: Optional[str] = None
    allergies: Optional[str] = None
    notes: Optional[str] = None


class PetOut(PetBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PetWithOwner(PetOut):
    owner: OwnerOut

    class Config:
        from_attributes = True


OwnerOut.model_rebuild()