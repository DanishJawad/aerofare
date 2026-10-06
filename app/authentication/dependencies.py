from typing import Annotated

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer

from ..commons.errors import ApiError
from ..database import DbSession
from .models import User
from .security import decode_access_token, InvalidToken, TokenPayload
from . import services

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

def _credentials_error() -> ApiError:
    # A function, not one shared module-level instance: re-raising the same
    # exception object keeps appending to its traceback on every request.
    return ApiError(
        status.HTTP_401_UNAUTHORIZED,
        "invalid_token",
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenPayload:
    try:
        return decode_access_token(token)
    except InvalidToken:
        raise _credentials_error()


# FastAPI caches a dependency's result per request, so if a route depends on
# both CurrentUser and CurrentTokenPayload, get_token_payload still only runs
# (and only hits Redis) once.
CurrentTokenPayload = Annotated[TokenPayload, Depends(get_token_payload)]


def get_current_user(payload: CurrentTokenPayload, db: DbSession) -> User:
    user = services.get_user(db, int(payload.subject))
    if user is None:
        raise _credentials_error()
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

def require_admin(current_user: CurrentUser) -> User:
    if not current_user.is_admin:
        raise ApiError(status.HTTP_403_FORBIDDEN, "admin_required", "Admin access required")
    return current_user

AdminUser = Annotated[User, Depends(require_admin)]
