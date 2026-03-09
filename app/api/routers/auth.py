from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_db_session
from app.deps.auth import get_current_user
from app.schemas.auth import Token, UserCreate, UserOut
from app.services.users import authenticate_user, create_user, get_user_by_username

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    existing = await get_user_by_username(session, data.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    try:
        user = await create_user(session, data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserOut(id=user.id, username=user.username, email=user.email)


@router.post("/token", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    user = await authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    token = create_access_token(subject=str(user.id), username=user.username)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(user=Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, email=user.email)

