# app/api/v1/endpoints/health.py
#
# WHY a detailed health check?
#
# A basic /health returning {"status": "ok"} only tells you
# the API process is alive. It doesn't tell you if:
# - The database is reachable
# - Redis is reachable
# - OpenAI API is accessible
# - Celery workers are running
#
# A production health check checks all dependencies.
# This is what load balancers, Kubernetes, and GCP Cloud Run use
# to decide if your service is healthy enough to receive traffic.
#
# TWO LEVELS OF HEALTH:
#
# /health/live  — "is the process alive?" (liveness probe)
#   Returns 200 as long as the process is running.
#   If this fails, the container is restarted.
#
# /health/ready — "can it serve traffic?" (readiness probe)
#   Checks DB, Redis, etc.
#   If this fails, traffic is temporarily routed elsewhere.
#   Process stays alive but doesn't receive requests.
#
# GCP Cloud Run uses these probes automatically.
#
# STATUS LEVELS:
#   healthy   — all dependencies up, serving traffic normally
#   degraded  — some non-critical dependencies down (e.g. Redis cache)
#               API still works, just slower (no caching)
#   unhealthy — critical dependencies down (e.g. DB)
#               cannot serve requests reliably

import time
import logging
from fastapi import APIRouter
from sqlalchemy import text
import redis as redis_lib
from app.db.session import SessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def check_database() -> dict:
    """
    Verify PostgreSQL connection by running a simple query.
    Measures latency to detect slow DB issues.
    """
    start = time.time()
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy",
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def check_redis() -> dict:
    """
    Verify Redis connection with a ping.
    Redis failure = no caching, no Celery task queue.
    """
    start = time.time()
    try:
        client = redis_lib.from_url(settings.REDIS_URL)
        client.ping()
        return {
            "status": "healthy",
            "latency_ms": int((time.time() - start) * 1000)
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def check_openai() -> dict:
    """
    Verify OpenAI API key is configured.
    We don't make a real API call (costs money) — just check key exists.
    In production: could make a cheap test call periodically.
    """
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-your-key-here":
        return {"status": "configured"}
    return {"status": "not_configured", "error": "OPENAI_API_KEY not set"}


@router.get("/live")
def liveness():
    """
    Liveness probe — is the process alive?
    Always returns 200 as long as FastAPI is running.
    GCP Cloud Run restarts container if this fails.
    """
    return {"status": "alive"}


@router.get("/ready")
def readiness():
    """
    Readiness probe — can this instance serve traffic?
    Checks all critical and non-critical dependencies.

    Returns 200 if healthy or degraded (still serving traffic).
    Returns 503 if unhealthy (cannot serve traffic reliably).

    Degraded example: Redis is down but DB is up.
    API works but AI responses won't be cached — slower but functional.
    """
    db_status = check_database()
    redis_status = check_redis()
    openai_status = check_openai()

    # Database is critical — without it, nothing works
    is_critical_healthy = db_status["status"] == "healthy"

    # Redis and OpenAI are important but not critical
    # API degrades gracefully without them
    all_healthy = (
        is_critical_healthy and
        redis_status["status"] == "healthy" and
        openai_status["status"] == "configured"
    )

    if all_healthy:
        overall_status = "healthy"
    elif is_critical_healthy:
        overall_status = "degraded"  # DB up but something else down
    else:
        overall_status = "unhealthy"  # DB down — cannot serve

    response = {
        "status": overall_status,
        "dependencies": {
            "database": db_status,
            "redis": redis_status,
            "openai": openai_status,
        }
    }

    # Return 503 only if unhealthy — degraded still gets 200
    # This tells the load balancer: degraded = still usable
    if overall_status == "unhealthy":
        from fastapi import Response
        from fastapi.responses import JSONResponse
        return JSONResponse(content=response, status_code=503)

    return response