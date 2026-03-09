from __future__ import annotations

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(scope="session")
async def prepared_engine(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
def session_factory(prepared_engine):
    return async_sessionmaker(prepared_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture()
def redis_client():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def app(session_factory, redis_client):
    application = create_app(start_cleanup_job=False, redis_client_override=redis_client)
    application.state.redis = redis_client

    async def override_get_db_session():
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_get_db_session
    return application


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

