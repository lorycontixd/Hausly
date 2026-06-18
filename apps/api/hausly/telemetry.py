"""Telemetry middleware and helpers for Azure Application Insights.

azure-monitor-opentelemetry auto-instruments FastAPI, SQLAlchemy, and httpx.
This module adds:
  - Unhandled-exception capture middleware
  - Span enrichment with user / household context
  - Structured-logging dimension helper
"""

import logging
from typing import Any

from fastapi import Request, Response
from opentelemetry import trace
from starlette.middleware.base import (BaseHTTPMiddleware,
                                       RequestResponseEndpoint)

logger = logging.getLogger("hausly")


def enrich_span(**attrs: Any) -> None:
    """Add custom attributes to the current OpenTelemetry span.

    Attributes appear as ``customDimensions`` in Application Insights and are
    prefixed with ``hausly.`` to avoid collisions.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(f"hausly.{key}", str(value))


def dims(**kw: Any) -> dict:
    """Build an ``extra`` dict for Python logging → App Insights custom dimensions."""
    return {
        "custom_dimensions": {k: str(v) for k, v in kw.items() if v is not None}
    }


class ExceptionTraceMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and logs them with request context.

    ``HTTPException`` and ``RequestValidationError`` are handled by FastAPI
    *before* reaching this layer, so only truly unexpected errors are caught.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.error(
                "Unhandled exception | %s %s",
                request.method,
                request.url.path,
                exc_info=True,
                extra=dims(
                    path=request.url.path,
                    method=request.method,
                    client_ip=request.client.host if request.client else "unknown",
                ),
            )
            raise
