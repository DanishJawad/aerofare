from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from typing import Self

class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone_number: str | None = None
    city: str
    country: str

class UserCreate(UserBase):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Ayesha Khan",
                    "email": "ayesha@example.com",
                    "phone_number": "+92 300 1234567",
                    "city": "Lahore",
                    "country": "PK",
                    "password": "a-long-passphrase",
                }
            ]
        }
    )

    password: str = Field(min_length=8 , max_length=72)

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_admin: bool

class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    city: str | None = None
    country: str | None = None

class Token(BaseModel):
    access_token: str
    token_type: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8 ,max_length=72)

    @model_validator(mode='after')
    def check_password(self) -> Self:
        if self.new_password == self.current_password:
            raise ValueError("new password cannot be same as old password")
        return self


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    # max_length: the token is hashed before lookup, so refuse to hash megabytes.
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)


class Message(BaseModel):
    message: str
