from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.session import engine
from app.jobs.expiry import run_expiry_cleanup_loop


def create_app(
    *,
    start_cleanup_job: bool = True,
    redis_client_override=None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.redis = redis_client_override or redis.from_url(
            settings.redis_url, decode_responses=True
        )

        app.state.expiry_task = None
        if start_cleanup_job:
            app.state.expiry_task = asyncio.create_task(
                run_expiry_cleanup_loop(
                    engine=engine,
                    redis_client=app.state.redis,
                    interval_seconds=settings.expiry_cleanup_interval_seconds,
                    batch_size=settings.expiry_cleanup_batch_size,
                )
            )
        try:
            yield
        finally:
            if app.state.expiry_task is not None:
                app.state.expiry_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await app.state.expiry_task
            with contextlib.suppress(Exception):
                await app.state.redis.aclose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
    app.include_router(api_router)
    return app


app = create_app()

