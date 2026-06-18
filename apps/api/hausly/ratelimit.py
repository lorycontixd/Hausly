import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from hausly.telemetry import dims
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger("hausly.ratelimit")

limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.warning(
        "Rate limit exceeded | %s %s",
        request.method,
        request.url.path,
        extra=dims(
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else "unknown",
        ),
    )
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
        headers={"Retry-After": str(exc.detail)},
    )