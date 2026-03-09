from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import User
from app.schemas.auth import UserCreate


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    res = await session.execute(select(User).where(User.username == username))
    return res.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    res = await session.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    user = User(
        username=data.username,
        email=str(data.email) if data.email else None,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise ValueError("User already exists") from e
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession, username: str, password: str
) -> User | None:
    user = await get_user_by_username(session, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

