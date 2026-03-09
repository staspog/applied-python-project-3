from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request


async def get_redis(request: Request):
    return request.app.state.redis

