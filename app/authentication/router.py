from fastapi import APIRouter, Depends
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm

from ..commons.errors import ApiError, error_responses
from ..database import DbSession
from .schemas import UserResponse, UserCreate, Token, UserUpdate, PasswordChange
from . import services
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

@router.post("/me/password", status_code=204, responses=error_responses(400, 401, 503))
def update_password(db: DbSession, current_user: CurrentUser, passwords: PasswordChange):
    """Change the logged-in user's password. `incorrect_password` if the current one is wrong."""
    try:
        services.change_password(db, current_user, passwords.current_password, passwords.new_password)
    except services.InvalidCredentials:
        raise ApiError(400, "incorrect_password", "Current Password is incorrect")

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

    return Token(access_token=create_access_token(str(user.id)),
                 token_type="bearer")

@router.post("/logout", status_code=204, responses=error_responses(401, 503))
def logout_user(token_payload: CurrentTokenPayload):
    """Revoke the current token. It stops working immediately, before its expiry time."""
    revoke_token(token_payload.jti, token_payload.expires_at)





