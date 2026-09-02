from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .schemas import UserCreate, UserUpdate
from .models import User
from .security import hash_password, verify_password

class EmailAlreadyExists(Exception):
    pass

class InvalidCredentials(Exception):
    pass

def create_user(db: Session, user: UserCreate) -> User:

    new_user = User(**user.model_dump(exclude={"password"}),
                    hashed_password = hash_password(user.password))
    try:
        db.add(new_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyExists()
    
    db.refresh(new_user)
    return new_user

def get_user(db:Session, user_id: int) -> User | None:
    return db.get(User, user_id)

def get_users(db:Session) -> list[User]:
    return list(db.execute(select(User)).scalars().all())

def update_user(db: Session, user: User, updated_user: UserUpdate) -> User:
    for key, value in updated_user.model_dump(exclude_unset=True).items():
        setattr(user, key, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExists() from exc

    db.refresh(user)
    return user

def change_password(db: Session, user: User, current_password: str , new_password: str) -> None:

    if not verify_password(current_password, user.hashed_password):
        raise InvalidCredentials()
    user.hashed_password = hash_password(new_password)
    db.commit()

def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentials()
    return user
        

    
