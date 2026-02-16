from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    birth_year: int
    birth_month: int

    @field_validator("birth_year")
    @classmethod
    def validate_birth_year(cls, value: int) -> int:
        current_year = datetime.now().year
        if value < 1900 or value > current_year:
            raise ValueError(f"birth_year must be between 1900 and {current_year}")
        return value

    @field_validator("birth_month")
    @classmethod
    def validate_birth_month(cls, value: int) -> int:
        if value < 1 or value > 12:
            raise ValueError("birth_month must be between 1 and 12")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    birth_year: int
    birth_month: int
