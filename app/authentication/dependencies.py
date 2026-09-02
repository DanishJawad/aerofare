from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from ..database import DbSession
from .models import User
from .security import decode_access_token, InvalidToken
from . import services

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    try:
        user_id = decode_access_token(token)
    except InvalidToken:
        raise _credentials_error

    user = services.get_user(db, int(user_id))
    if user is None:
        raise _credentials_error
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

def require_admin(current_user: CurrentUser) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

AdminUser = Annotated[User, Depends(require_admin)]


