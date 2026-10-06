import logging
import re
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .log_config import request_id_var
from .middleware import REQUEST_ID_HEADER

logger = logging.getLogger("aerofare.errors")


# ------------------------------------------------------------------ the shape


class ErrorDetail(BaseModel):
    field: str | None  # None for errors that belong to the whole body
    message: str


class ErrorBody(BaseModel):
    code: str  # stable, for programs to switch on: "not_enough_seats"
    message: str  # for people; wording may change without notice
    details: list[ErrorDetail] | None
    request_id: str  # same value as the X-Request-ID response header


class ErrorResponse(BaseModel):
    """Every error from this API has exactly this shape."""

    error: ErrorBody


class ApiError(HTTPException):
    """An HTTPException that also carries a machine-readable code.

    Subclassing HTTPException means everything FastAPI already does with it
    keeps working (including the `headers` argument for WWW-Authenticate)."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """For a route's `responses=`: documents these error statuses in /docs as
    returning our ErrorResponse envelope. Without it, /docs only lists the
    success response, and FastAPI's built-in 422 describes a shape this API
    no longer returns."""
    return {
        status: {"model": ErrorResponse, "description": HTTPStatus(status).phrase}
        for status in statuses
    }


# 422 and 500 can happen on any route, so they are declared once on the app
# instead of on every route.
COMMON_ERROR_RESPONSES = error_responses(422, 500)


# ------------------------------------------------------------------ building responses


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request_id_var.get()
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details, request_id=request_id)
    )
    # The header is set here as well as in the request middleware. The 500
    # handler below runs outside the middleware, so without this line crashes
    # would be the one kind of response with no X-Request-ID.
    response_headers = {**(headers or {}), REQUEST_ID_HEADER: request_id}
    return JSONResponse(
        status_code=status_code, content=body.model_dump(), headers=response_headers
    )


def _default_code(status_code: int) -> str:
    """404 -> "not_found", 405 -> "method_not_allowed". Used for errors that
    nobody gave a specific code: unknown URLs, wrong methods, a missing token."""
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return f"http_{status_code}"
    return re.sub(r"\W+", "_", phrase.lower()).strip("_")


def _field_path(loc: tuple) -> str | None:
    # loc[0] says where FastAPI found the value ("body", "query", "path"), which
    # the client already knows. What's left is the field: ("body", "price") ->
    # "price". A rule that spans several fields has loc == ("body",) -> None.
    return ".".join(str(part) for part in loc[1:]) or None


# ------------------------------------------------------------------ handlers


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = getattr(exc, "code", None) or _default_code(exc.status_code)
    return _error_response(exc.status_code, code, str(exc.detail), headers=exc.headers)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Only loc and msg are read. Pydantic's error dicts can also hold `ctx`
    # (sometimes a raw exception object) and `input` (what the user sent),
    # which are not JSON-serialisable or not safe to echo back.
    details = [
        ErrorDetail(
            field=_field_path(error["loc"]),
            message=error["msg"].removeprefix("Value error, "),
        )
        for error in exc.errors()
    ]
    return _error_response(422, "validation_error", "Request validation failed.", details)


async def redis_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    # Every authenticated request checks the token blacklist in Redis. If Redis
    # is down we cannot tell a logged-out token from a valid one, so the request
    # is refused (fail closed) instead of being let through.
    logger.error("Redis unavailable: %s", exc)
    return _error_response(
        503, "service_unavailable", "Service temporarily unavailable. Try again shortly."
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # The client gets a generic message: the exception text can contain SQL,
    # file paths or other internals. The real traceback goes to the log with
    # the same request_id the client receives, so a user's report can be
    # matched to it.
    logger.error("Unhandled exception", exc_info=exc)
    return _error_response(500, "internal_error", "Something went wrong on our side.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RedisConnectionError, redis_unavailable_handler)
    app.add_exception_handler(RedisTimeoutError, redis_unavailable_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
