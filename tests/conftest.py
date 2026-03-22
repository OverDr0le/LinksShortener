"""
Shared fixtures for the entire test suite.

Hierarchy
─────────
conftest.py          ← this file (session-scoped engine + per-test DB + app overrides)
unit/                ← pure-logic tests, no I/O
functional/          ← FastAPI TestClient / httpx tests against a real in-process app
load/                ← Locust scenario
"""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ── patch environment BEFORE any app module is imported ──────────────────────
import os
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import types as _t, String as _S


class _UUIDasStr(_t.TypeDecorator):
    """UUID stored as VARCHAR(36) — works in both PostgreSQL and SQLite."""
    impl = _S(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class _PatchedUUID(_UUIDasStr):
    """Drop-in замена для sqlalchemy.dialects.postgresql.UUID."""
    def __init__(self, as_uuid=True, **kw):
        super().__init__(**kw)
        self.cache_ok = True


# Патч применяется до импорта моделей, поэтому mapped_column(UUID(as_uuid=True))
# будет создавать VARCHAR(36) вместо нативного PostgreSQL UUID.
# Без этого SQLite возвращает rowid как float, и uuid.UUID(float) падает с
# AttributeError: 'float' object has no attribute 'replace'.
_pg.UUID = _PatchedUUID

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASS", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("SECRET", "super-secret-test-key-at-least-32-chars!!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

# ── FastAPICache stub — иначе startup пытается подключиться к Redis ──────────
import fastapi_cache
fastapi_cache.FastAPICache.init = MagicMock()

# ── app imports (after env + patch) ──────────────────────────────────────────
from app.database import Base, get_session          # noqa: E402
from app.core.redis import get_redis                # noqa: E402
from app.main import app                            # noqa: E402
from app.models.link import Link                    # noqa: E402
from app.models.user import User                    # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# In-memory SQLite engine (session-scoped — created once for the whole run)
# ─────────────────────────────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create all tables once; drop them after the session."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test transactional session that is rolled back after every test,
    so tests remain completely isolated.
    """
    session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, autocommit=False, autoflush=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Redis mock  (per-test)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_redis():
    """Async mock that behaves like redis.asyncio.Redis."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)   # cache miss by default
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Синхронный TestClient — стандартный способ для FastAPI-тестов.
# Запускает ASGI-приложение в фоновом потоке с собственным event loop,
# поэтому тесты остаются обычными def-функциями без async/await.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def client(db_session, mock_redis):
    async def override_get_session():
        yield db_session

    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Reusable domain objects
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def sample_link(sample_user_id) -> Link:
    return Link(
        id=uuid.uuid4(),
        original_url="https://example.com/very/long/path",
        short_url="abc123",
        user_id=sample_user_id,
        created_at=datetime.now(timezone.utc),
        expires_at=None,
        click_count=0,
        last_accessed_at=None,
    )


@pytest.fixture
def anon_link() -> Link:
    """Link created without a registered user."""
    return Link(
        id=uuid.uuid4(),
        original_url="https://anon.example.com",
        short_url="anon42",
        user_id=None,
        created_at=datetime.now(timezone.utc),
        expires_at=None,
        click_count=0,
        last_accessed_at=None,
    )
