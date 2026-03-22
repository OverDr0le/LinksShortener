"""
Functional-test fixtures.

Provides three synchronous TestClient variants — the standard FastAPI way:
  • authenticated_client  — owner user (sample_user_id)
  • other_client          — a different, non-owner user
  • anon_client           — no authenticated user at all

All clients share the same in-memory SQLite session and mocked Redis
provided by the root conftest.  Because TestClient manages its own event
loop internally, every test function is plain `def` — no async/await
overhead at the HTTP layer.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.user import current_user, current_user_optional
from app.core.redis import get_redis
from app.database import get_session
from app.main import app
from app.models.user import User


# ── helpers ───────────────────────────────────────────────────────────────────────

def _make_user(uid: uuid.UUID, email: str) -> User:
    """Build a minimal in-memory User object (not persisted to the DB)."""
    user = User()
    user.id = uid
    user.email = email
    user.is_active = True
    user.is_superuser = False
    user.is_verified = True
    return user


# ── fixtures ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def _app_overrides(db_session, mock_redis):
    """
    Устанавливает переопределения get_session и get_redis один раз на тест.
    Все клиенты внутри одного теста используют одну и ту же db_session и mock_redis.
    Переопределения current_user / current_user_optional каждый клиент
    устанавливает сам перед запросом.
    """
    async def override_session():
        yield db_session

    async def override_redis():
        yield mock_redis

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_redis] = override_redis
    yield db_session, mock_redis
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_redis, None)


class _UserClient:
    """
    Тонкая обёртка над TestClient, которая перед каждым запросом
    подставляет нужного пользователя в dependency_overrides.
    Это гарантирует правильный override даже когда несколько клиентов
    существуют одновременно в одном тесте.
    """
    _METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

    def __init__(self, tc: TestClient, user: User | None):
        self._tc = tc
        self._user = user

    def _set_user_overrides(self):
        u = self._user
        app.dependency_overrides[current_user] = lambda: u
        app.dependency_overrides[current_user_optional] = lambda: u

    def __getattr__(self, name):
        attr = getattr(self._tc, name)
        if name in self._METHODS:
            def _patched(*args, **kwargs):
                self._set_user_overrides()
                return attr(*args, **kwargs)
            return _patched
        return attr


@pytest.fixture
def authenticated_client(_app_overrides, sample_user_id):
    """TestClient pre-authenticated as the link owner."""
    owner = _make_user(sample_user_id, "owner@example.com")
    tc = TestClient(app, raise_server_exceptions=True)
    with tc:
        yield _UserClient(tc, owner)


@pytest.fixture
def other_client(_app_overrides, other_user_id):
    """TestClient authenticated as a *different*, non-owner user."""
    other = _make_user(other_user_id, "other@example.com")
    tc = TestClient(app, raise_server_exceptions=True)
    with tc:
        yield _UserClient(tc, other)


@pytest.fixture
def anon_client(_app_overrides):
    """TestClient with no authenticated user (anonymous)."""
    tc = TestClient(app, raise_server_exceptions=True)
    with tc:
        yield _UserClient(tc, None)
