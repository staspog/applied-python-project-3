from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: EmailStr | None = None


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

