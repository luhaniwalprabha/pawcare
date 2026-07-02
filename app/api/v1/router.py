# app/api/v1/router.py
#
# Central router — single place to see all API surface area.
#
# PATTERN: each feature owns its own router file.
# Adding a feature = create endpoints file + one line here.
# This keeps main.py clean and each feature independently testable.
#
# PREFIX DESIGN:
#   /api/v1/        — versioned API (breaking changes → /api/v2/)
#   /auth/          — authentication
#   /patients/      — owners and pets
#   /appointments/  — scheduling
#   /medical-records/ — clinical notes
#   /billing/       — invoices
#   /ai/            — AI features
#   /health/        — observability

from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    patients,
    appointments,
    medical_records,
    billing,
    ai,
    health,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["appointments"])
api_router.include_router(medical_records.router, prefix="/medical-records", tags=["medical-records"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(health.router, prefix="/health", tags=["health"])