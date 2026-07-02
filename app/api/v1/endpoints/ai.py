# app/api/v1/endpoints/ai.py
#
# AI feature endpoints — thin layer over the AI service.
#
# DESIGN PRINCIPLE: endpoints should be thin.
# The endpoint's job is:
#   1. Validate input (Pydantic does this)
#   2. Fetch data from DB if needed
#   3. Call the service layer
#   4. Return the response
#
# Business logic and AI logic live in app/ai/service.py, not here.
# This makes the AI service testable independently of HTTP.
#
# RATE LIMITING NOTE:
# AI endpoints are expensive (OpenAI costs money).
# In production, add per-user rate limiting here.
# We log usage per request for now — rate limiting comes in Part C.
#
# RESPONSE DESIGN:
# Each response includes:
#   - The AI result
#   - from_cache: bool (helps with debugging and cost tracking)
#   - fallback: bool (tells caller if AI failed and this is a fallback)
# This transparency is important for production systems.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.db.session import get_db
from app.models.patient import Pet, Owner
from app.models.clinic import MedicalRecord
from app.core.security import get_current_user
from app.ai import service as ai_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Request/Response schemas ─────────────────────────────────────────────────

class TriageRequest(BaseModel):
    pet_id: int
    symptoms: str  # free text from owner — will be sanitized in service layer


class TriageResponse(BaseModel):
    urgency_level: str
    urgency_score: int
    reasoning: str
    recommended_action: str
    warning_signs: list
    confidence: float
    from_cache: bool
    fallback: bool = False


class HistorySummaryResponse(BaseModel):
    summary: str
    key_conditions: list
    current_medications: list
    allergies: list
    recent_concerns: list
    flags: list
    from_cache: bool
    fallback: bool = False


class CareInstructionsResponse(BaseModel):
    summary: str
    medications: list
    home_care: list
    diet_restrictions: list
    activity_restrictions: list
    warning_signs: list
    follow_up: str
    emergency_note: str
    from_cache: bool
    fallback: bool = False


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/triage", response_model=TriageResponse)
def triage_symptoms(
    payload: TriageRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Assess urgency of symptoms before booking an appointment.

    Who uses this: receptionist or owner when calling to describe symptoms.
    Output helps decide: book routine appointment or send to emergency.

    The AI service handles caching and fallback — this endpoint
    just fetches pet context and delegates.
    """
    # Fetch pet with owner details for context injection into prompt
    pet = db.query(Pet).filter(Pet.id == payload.pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    owner = db.query(Owner).filter(Owner.id == pet.owner_id).first()

    # Calculate approximate age from date of birth
    age = "Unknown"
    if pet.date_of_birth:
        from datetime import date
        today = date.today()
        years = today.year - pet.date_of_birth.year
        months = today.month - pet.date_of_birth.month
        if months < 0:
            years -= 1
            months += 12
        age = f"{years} years {months} months" if years > 0 else f"{months} months"

    logger.info(
        f"Triage requested | pet_id={pet.id} | user_id={current_user.id}"
    )

    result = ai_service.triage_symptoms(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "Unknown",
        age=age,
        allergies=pet.allergies or "",
        symptoms=payload.symptoms,
    )

    return result


@router.get("/history-summary/{pet_id}", response_model=HistorySummaryResponse)
def get_history_summary(
    pet_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate AI clinical summary of pet's medical history.

    Who uses this: vet before starting a consultation.
    Instead of reading through 20 visit records, vet gets a
    concise summary with flags for important issues.

    Records are passed as structured data to the AI service
    which formats them into a readable prompt.
    """
    pet = db.query(Pet).filter(Pet.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # Fetch all medical records ordered most recent first
    records = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.pet_id == pet_id)
        .order_by(MedicalRecord.visit_date.desc())
        .all()
    )

    if not records:
        # Return meaningful response even with no history
        return {
            "summary": f"{pet.name} has no previous medical records.",
            "key_conditions": [],
            "current_medications": [],
            "allergies": [pet.allergies] if pet.allergies else [],
            "recent_concerns": [],
            "flags": ["First visit — no medical history available"],
            "from_cache": False,
            "fallback": False,
        }

    # Convert SQLAlchemy objects to dicts for the AI service
    # AI service doesn't know about SQLAlchemy models — clean separation
    records_data = [
        {
            "visit_date": str(r.visit_date),
            "chief_complaint": r.chief_complaint,
            "diagnosis": r.diagnosis,
            "treatment": r.treatment,
            "prescriptions": r.prescriptions,
            "weight_at_visit": r.weight_at_visit,
            "notes": r.notes,
        }
        for r in records
    ]

    logger.info(
        f"History summary requested | pet_id={pet_id} | "
        f"records={len(records)} | user_id={current_user.id}"
    )

    result = ai_service.summarize_medical_history(
        pet_name=pet.name,
        species=pet.species.value,
        breed=pet.breed or "Unknown",
        dob=str(pet.date_of_birth) if pet.date_of_birth else None,
        weight=str(pet.weight_kg) if pet.weight_kg else None,
        records=records_data,
    )

    return result


@router.get("/care-instructions/{record_id}", response_model=CareInstructionsResponse)
def get_care_instructions(
    record_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate post-visit care instructions from a medical record.

    Who uses this: receptionist when checking out a patient.
    The instructions are printed or emailed to the owner.

    Cached for 24 hours — instructions for a completed visit are static.
    """
    record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")

    pet = db.query(Pet).filter(Pet.id == record.pet_id).first()
    owner = db.query(Owner).filter(Owner.id == pet.owner_id).first() if pet else None

    logger.info(
        f"Care instructions requested | record_id={record_id} | "
        f"user_id={current_user.id}"
    )

    result = ai_service.generate_care_instructions(
        pet_name=pet.name if pet else "your pet",
        species=pet.species.value if pet else "animal",
        owner_name=owner.full_name if owner else "Owner",
        chief_complaint=record.chief_complaint or "",
        diagnosis=record.diagnosis or "",
        treatment=record.treatment or "",
        prescriptions=record.prescriptions or "",
        follow_up_required=record.follow_up_required,
        follow_up_date=str(record.follow_up_date) if record.follow_up_date else None,
        notes=record.notes or "",
    )

    return result