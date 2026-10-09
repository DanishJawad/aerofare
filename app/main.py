from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .airports.router import router as airport_router
from .authentication.router import router as auth_router
from .bookings import models as _booking_models  # noqa: F401 - registers the table
from .bookings.router import router as booking_router
from .commons.errors import COMMON_ERROR_RESPONSES, register_error_handlers
from .commons.log_config import configure_logging
from .commons.middleware import request_context
from .database import settings
from .flights.router import router as flight_router
from .payments import models as _payment_models  # noqa: F401 - registers the table
from .payments.router import router as payment_router

configure_logging(settings.log_level, settings.log_format)

DESCRIPTION = """
Flight booking API: search flights, book seats, pay, cancel, and manage flights as an admin.

**Authentication.** `POST /users/signup`, then `POST /users/login` (form fields: `username` is the
email address, plus `password`). Click **Authorize** above and enter the same email and password.
Logging out revokes the token immediately.

**Errors.** Every error, whatever its status, has the same shape:
`{"error": {"code", "message", "details", "request_id"}}`. Switch on `code`, show `message`, and
quote `request_id` (also sent as the `X-Request-ID` header) when reporting a problem.
"""

TAGS = [
    {"name": "users", "description": "Sign up, log in and out, manage your profile. Listing users is admin only."},
    {"name": "airports", "description": "Reading is public. Creating and editing is admin only."},
    {"name": "flights", "description": "Searching and reading is public. Creating and editing is admin only."},
    {"name": "bookings", "description": "Booking reserves seats and creates a completed payment in one transaction. Cancelling returns the seats and refunds the payment."},
    {"name": "payments", "description": "Payments are created by bookings. Admins can refund."},
]

app = FastAPI(
    title="Aerofare",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    responses=COMMON_ERROR_RESPONSES,
)

app.middleware("http")(request_context)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_headers=["*"],
    allow_methods=["*"]
)

app.include_router(airport_router)
app.include_router(flight_router)
app.include_router(auth_router)
app.include_router(booking_router)
app.include_router(payment_router)
