import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from ..commons.errors import ApiError, error_responses
from ..commons.rate_limit import enforce_rate_limit
from ..database import DbSession
from ..notifications.tasks import enqueue_password_reset
from .schemas import ForgotPassword, Message, PasswordChange, ResetPassword, Token, UserCreate, UserResponse, UserUpdate
from . import password_reset, services
from .security import create_access_token, revoke_token
from .dependencies import CurrentUser, AdminUser, CurrentTokenPayload

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse, responses=error_responses(401, 503))
def read_me(current_user: CurrentUser):
    """The logged-in user's profile."""
    return current_user

@router.patch("/me", response_model=UserResponse, responses=error_responses(401, 409, 503))
def update_me(db: DbSession, current_user: CurrentUser , updated_user: UserUpdate):
    """Update the logged-in user's profile. `email_already_registered` if the new email is taken."""
    try:
        updated_user = services.update_user(db, current_user, updated_user)
        return updated_user
    except services.EmailAlreadyExists:
        raise ApiError(409, "email_already_registered", "Email already registered")

@router.post("/me/password", response_model=Token, responses=error_responses(400, 401, 503))
def update_password(db: DbSession, current_user: CurrentUser, passwords: PasswordChange):
    """Change the logged-in user's password. `incorrect_password` if the current one is wrong.

    Every token issued before the change stops working, including the one used for this request.
    The response holds a new token, so the session that made the change stays logged in."""
    try:
        services.change_password(db, current_user, passwords.current_password, passwords.new_password)
    except services.InvalidCredentials:
        raise ApiError(400, "incorrect_password", "Current Password is incorrect")
    return Token(access_token=create_access_token(str(current_user.id), current_user.token_version),
                 token_type="bearer")

@router.get("", response_model=list[UserResponse], responses=error_responses(401, 403, 503))
def list_users(admin: AdminUser, db: DbSession):
    """List all users. Admin only."""
    return services.get_users(db)

@router.get("/{user_id}", response_model=UserResponse, responses=error_responses(401, 403, 404, 503))
def get_user_by_id(admin: AdminUser, user_id: int, db: DbSession):
    """Get one user by id. Admin only."""
    user = services.get_user(db, user_id)
    if user is None:
        raise ApiError(404, "user_not_found", "User not found")
    return user

@router.post("/signup", response_model=UserResponse , status_code=201, responses=error_responses(409))
def create_user(db: DbSession, new_user: UserCreate):
    """Create an account. `email_already_registered` if the email is taken."""
    try:
        return services.create_user(db , new_user)
    except services.EmailAlreadyExists:
        raise ApiError(409, "email_already_registered", "Email already registered")

@router.post("/login" , response_model=Token, responses=error_responses(401))
def login_user(form: Annotated[OAuth2PasswordRequestForm,  Depends()] ,db: DbSession):
    """Log in and receive an access token. Form-encoded, not JSON: `username` is the email address."""
    try:
        user = services.authenticate_user(db, form.username, form.password)
    except services.InvalidCredentials:
        raise ApiError(401, "invalid_credentials", "Incorrect email or password")

    return Token(access_token=create_access_token(str(user.id), user.token_version),
                 token_type="bearer")

@router.post("/logout", status_code=204, responses=error_responses(401, 503))
def logout_user(token_payload: CurrentTokenPayload):
    """Revoke the current token. It stops working immediately, before its expiry time."""
    revoke_token(token_payload.jti, token_payload.expires_at)


# Forgot-password limits. The per-address limit stops one inbox being flooded
# with reset emails. The per-IP limit is higher, because one IP can be a whole
# office or a university, and stops one machine trying many addresses.
FORGOT_WINDOW_SECONDS = 15 * 60
FORGOT_LIMIT_PER_EMAIL = 3
FORGOT_LIMIT_PER_IP = 10


@router.post("/forgot-password", response_model=Message, status_code=202, responses=error_responses(429, 503))
def forgot_password(body: ForgotPassword, request: Request, db: DbSession):
    """Email a password reset link, if an account has this address.

    The answer is always the same 202, whether or not the address is registered, so this cannot be
    used to find out who has an account. Limited to 3 requests per address and 10 per IP every 15
    minutes: `rate_limited`."""
    ip = request.client.host if request.client else "unknown"
    # Counted before the account lookup, and for unknown addresses too, so the
    # limit behaves identically whether or not the address exists.
    enforce_rate_limit(f"ratelimit:forgot:ip:{ip}", FORGOT_LIMIT_PER_IP, FORGOT_WINDOW_SECONDS)
    email_hash = hashlib.sha256(body.email.lower().encode()).hexdigest()
    enforce_rate_limit(f"ratelimit:forgot:email:{email_hash}", FORGOT_LIMIT_PER_EMAIL, FORGOT_WINDOW_SECONDS)

    user = services.get_user_by_email(db, body.email)
    if user is not None:
        token = password_reset.create_reset_token(user.id)
        enqueue_password_reset(user.id, token)
    return Message(message="If an account exists for that email, a reset link is on its way.")


@router.post("/reset-password", status_code=204, responses=error_responses(400, 503))
def reset_password(body: ResetPassword, db: DbSession):
    """Set a new password using the token from the reset email. `invalid_reset_token` if it is
    unknown, expired or already used. Every existing login is ended; log in again afterwards."""
    try:
        services.reset_password(db, body.token, body.new_password)
    except services.InvalidResetToken:
        raise ApiError(400, "invalid_reset_token", "This reset link is invalid or has expired")

