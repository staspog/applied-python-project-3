from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db_session
from app.services.users import get_user_by_id

oauth2_required = OAuth2PasswordBearer(tokenUrl="/auth/token")
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_required)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_optional)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
    except Exception:  # noqa: BLE001
        return None
    return await get_user_by_id(session, user_id)

