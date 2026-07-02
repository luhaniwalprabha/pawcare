# app/core/logging.py
#
# WHY structured logging?
#
# Default Python logging: "User created appointment at 2pm"
# Structured logging:     {"event": "appointment_created", "user_id": 42, "latency_ms": 45}
#
# Structured logs can be:
# - Searched: "show all requests where latency_ms > 1000"
# - Aggregated: "count errors by endpoint in last hour"
# - Alerted on: "alert if error_rate > 5% in 5 minutes"
#
# Tools like Datadog, Grafana, GCP Cloud Logging parse JSON logs automatically.
# Plain text logs require custom parsing — painful at scale.
#
# CORRELATION IDs (request_id):
# Every request gets a unique ID (UUID).
# This ID is attached to every log line for that request.
# When debugging: "find all logs for request abc-123" shows the full journey.
# Without this: impossible to trace a single request through distributed logs.
#
# The middleware intercepts every request:
#   request comes in → generate request_id → attach to context
#   → process request → log result with timing

import time
import uuid
import logging
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configure root logger to output JSON
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every request with:
    - Unique request_id for tracing
    - HTTP method, path, status code
    - Response time in milliseconds
    - User agent (for debugging client issues)

    Skips health check endpoint — no value logging those.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip logging for health checks — they're noisy and uninteresting
        if request.url.path == "/health":
            return await call_next(request)

        # Generate unique request ID
        # This gets passed to all downstream logs so you can
        # trace a single request across all log lines
        request_id = str(uuid.uuid4())[:8]  # short UUID for readability
        start_time = time.time()

        # Attach request_id to request state so endpoints can log it
        request.state.request_id = request_id

        # Process the request
        response = await call_next(request)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log as structured JSON
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "user_agent": request.headers.get("user-agent", ""),
        }

        # Log level based on status code
        if response.status_code >= 500:
            logger.error(json.dumps(log_data))
        elif response.status_code >= 400:
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

        # Add request_id to response headers
        # Client can use this when reporting bugs: "request_id: abc-123 failed"
        response.headers["X-Request-ID"] = request_id

        return response