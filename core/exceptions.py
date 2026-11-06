
from fastapi import Request
from fastapi.responses import JSONResponse

from core.logger import logger


class APIException(Exception):
    """Base exception for expected application errors."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def api_exception_handler(request: Request, exc: APIException):
    """Handle expected application errors."""

    logger.warning(
        "Expected application error | "
        "Status: %s | Path: %s | Message: %s",
        exc.status_code,
        request.url.path,
        exc.message,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
        },
    )


async def global_exception_handler(request: Request, exc: Exception):
    """Log unexpected exceptions securely and return a generic response."""

    logger.error(
        "CRITICAL UNHANDLED ERROR | Method: %s | Path: %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error. Please try again later.",
        },
    )
