from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.db.session import get_db
from app.models.patient import Owner, Pet
from app.schemas.patient import (
    OwnerCreate, OwnerUpdate, OwnerOut,
    PetCreate, PetUpdate, PetOut, PetWithOwner
)
from app.core.security import get_current_user, require_roles

router = APIRouter()


# ─── Owners ───────────────────────────────────────────────

@router.get("/owners", response_model=List[OwnerOut])
def list_owners(
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Owner).options(joinedload(Owner.pets))
    if search:
        q = q.filter(
            Owner.full_name.ilike(f"%{search}%") |
            Owner.email.ilike(f"%{search}%") |
            Owner.phone.ilike(f"%{search}%")
        )
    return q.offset(skip).limit(limit).all()


@router.post("/owners", response_model=OwnerOut, status_code=201)
def create_owner(
    payload: OwnerCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if db.query(Owner).filter(Owner.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Owner with this email already exists")
    owner = Owner(**payload.model_dump())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


@router.get("/owners/{owner_id}", response_model=OwnerOut)
def get_owner(
    owner_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    owner = db.query(Owner).options(joinedload(Owner.pets)).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return owner


@router.patch("/owners/{owner_id}", response_model=OwnerOut)
def update_owner(
    owner_id: int,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(owner, field, value)
    db.commit()
    db.refresh(owner)
    return owner


@router.delete("/owners/{owner_id}", status_code=204)
def delete_owner(
    owner_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    db.delete(owner)
    db.commit()


# ─── Pets ─────────────────────────────────────────────────

@router.get("/pets", response_model=List[PetWithOwner])
def list_pets(
    search: Optional[str] = Query(None, description="Search by pet name or breed"),
    species: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(Pet).options(joinedload(Pet.owner))
    if search:
        q = q.filter(Pet.name.ilike(f"%{search}%") | Pet.breed.ilike(f"%{search}%"))
    if species:
        q = q.filter(Pet.species == species)
    return q.offset(skip).limit(limit).all()


@router.post("/pets", response_model=PetOut, status_code=201)
def create_pet(
    payload: PetCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if not db.query(Owner).filter(Owner.id == payload.owner_id).first():
        raise HTTPException(status_code=404, detail="Owner not found")
    if payload.microchip_number:
        existing = db.query(Pet).filter(Pet.microchip_number == payload.microchip_number).first()
        if existing:
            raise HTTPException(status_code=400, detail="Microchip number already registered")
    pet = Pet(**payload.model_dump())
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


@router.get("/pets/{pet_id}", response_model=PetWithOwner)
def get_pet(
    pet_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    pet = db.query(Pet).options(joinedload(Pet.owner)).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


@router.patch("/pets/{pet_id}", response_model=PetOut)
def update_pet(
    pet_id: int,
    payload: PetUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pet, field, value)
    db.commit()
    db.refresh(pet)
    return pet


@router.delete("/pets/{pet_id}", status_code=204)
def delete_pet(
    pet_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin", "vet")),
):
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    db.delete(pet)
    db.commit()