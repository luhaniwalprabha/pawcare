# main.py
#
# FastAPI application entry point.
#
# WHAT CHANGED IN PHASE 4:
# 1. Added RequestLoggingMiddleware — every request gets logged with request_id
# 2. Added AI endpoints under /api/v1/ai
# 3. Added health check endpoints under /api/v1/health
# 4. Added lifespan handler — clean startup/shutdown logging
#
# MIDDLEWARE ORDER MATTERS:
# Middleware is applied in reverse order of registration.
# CORS must be outermost (first registered) so it handles preflight requests
# before any other middleware touches them.
# Logging is innermost so it captures the true request latency.
#
# LIFESPAN:
# Code before `yield` runs on startup.
# Code after `yield` runs on shutdown.
# Use for: DB connection warmup, cache warming, graceful shutdown.

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import RequestLoggingMiddleware
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"PawCare API starting | env={settings.ENVIRONMENT}")
    yield
    # Shutdown
    logger.info("PawCare API shutting down")


app = FastAPI(
    title="PawCare API",
    description="Production-grade pet hospital management platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — must be registered first (outermost middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging — captures every request with request_id and latency
app.add_middleware(RequestLoggingMiddleware)

# All API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    """
    Simple top-level health — for quick checks.
    Detailed health is at /api/v1/health/ready
    """
    return {"status": "ok", "env": settings.ENVIRONMENT}