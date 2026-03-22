"""
Unit-tests for small pieces that are easy to miss in coverage:

  • Link.__repr__  and  User.__repr__
  • LinkService._cache_key
  • LinkService.get_link_service  (async generator dependency)
  • UserManager lifecycle hooks  (on_after_register, on_after_forgot_password,
                                   on_after_request_verify)
  • celery delete_link_task  (the inner async function via mocked DB session)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.link import Link
from app.models.user import User
from app.services.link_service import LinkService, get_link_service
from app.auth.manager import UserManager


# ── Link.__repr__ ─────────────────────────────────────────────────────────────

class TestLinkRepr:

    def test_repr_contains_short_url(self):
        link = Link(
            id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            original_url="https://repr.test",
            short_url="repr-test",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        r = repr(link)
        assert "repr-test" in r
        assert "repr.test" in r

    def test_repr_is_string(self):
        link = Link(
            id=uuid.uuid4(),
            original_url="https://x.com",
            short_url="x",
            created_at=datetime.now(timezone.utc),
        )
        assert isinstance(repr(link), str)


# ── User.__repr__ ─────────────────────────────────────────────────────────────

class TestUserRepr:

    def test_repr_contains_email(self):
        user = User()
        user.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        user.email = "test@example.com"
        user.created_at = datetime(2025, 1, 1)
        r = repr(user)
        assert "test@example.com" in r

    def test_repr_is_string(self):
        user = User()
        user.id = uuid.uuid4()
        user.email = "x@y.com"
        user.created_at = datetime.now()
        assert isinstance(repr(user), str)


# ── LinkService._cache_key ────────────────────────────────────────────────────

class TestCacheKey:

    def test_cache_key_format(self):
        svc = LinkService(repo=AsyncMock(), redis=AsyncMock())
        assert svc._cache_key("abc123") == "short_url:abc123"

    def test_cache_key_used_consistently(self):
        """The same code must always produce the same key."""
        svc = LinkService(repo=AsyncMock(), redis=AsyncMock())
        assert svc._cache_key("XYZ") == svc._cache_key("XYZ")

    def test_different_codes_produce_different_keys(self):
        svc = LinkService(repo=AsyncMock(), redis=AsyncMock())
        assert svc._cache_key("aaa") != svc._cache_key("bbb")


# ── get_link_service  (async generator) ──────────────────────────────────────

class TestGetLinkServiceGenerator:
    """
    get_link_service is a FastAPI dependency declared as an async generator.
    We must drive it manually to cover both the yield and the implicit return.
    """

    @pytest.mark.asyncio
    async def test_yields_link_service_instance(self):
        mock_repo = AsyncMock()
        mock_redis = AsyncMock()

        gen = get_link_service(repo=mock_repo, redis=mock_redis)
        svc = await gen.__anext__()

        assert isinstance(svc, LinkService)
        assert svc.repo is mock_repo
        assert svc.redis is mock_redis

        # Exhaust the generator (covers the implicit StopAsyncIteration)
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


# ── UserManager hooks ─────────────────────────────────────────────────────────

class TestUserManagerHooks:
    """
    The three lifecycle hooks just call print().
    We verify they run without error and produce output.
    """

    def _make_manager(self) -> UserManager:
        user_db = MagicMock()
        return UserManager(user_db)

    def _make_user(self) -> User:
        user = User()
        user.id = uuid.uuid4()
        user.email = "hook@example.com"
        user.created_at = datetime.now()
        return user

    @pytest.mark.asyncio
    async def test_on_after_register(self, capsys):
        mgr = self._make_manager()
        user = self._make_user()
        await mgr.on_after_register(user)
        captured = capsys.readouterr().out
        assert str(user.id) in captured

    @pytest.mark.asyncio
    async def test_on_after_forgot_password(self, capsys):
        mgr = self._make_manager()
        user = self._make_user()
        await mgr.on_after_forgot_password(user, token="reset-token-123")
        captured = capsys.readouterr().out
        assert "reset-token-123" in captured

    @pytest.mark.asyncio
    async def test_on_after_request_verify(self, capsys):
        mgr = self._make_manager()
        user = self._make_user()
        await mgr.on_after_request_verify(user, token="verify-token-456")
        captured = capsys.readouterr().out
        assert "verify-token-456" in captured


# ── Celery delete_link_task ───────────────────────────────────────────────────

class TestDeleteLinkTask:
    """
    delete_link_task is a synchronous Celery task that internally runs an
    async function via asyncio.run().  We mock out the DB session maker and
    the repository so no real I/O occurs.
    """

    def test_task_deletes_existing_link(self):
        link_id = str(uuid.uuid4())
        mock_link = MagicMock()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_link)
        mock_repo.delete = AsyncMock()

        # Patch at the celery_app module level
        with patch("app.tasks.celery_app.async_session_maker") as mock_sm, \
             patch("app.tasks.celery_app.LinkRepository", return_value=mock_repo):

            # async_session_maker() is used as an async context manager
            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.celery_app import delete_link_task
            delete_link_task(link_id)

        mock_repo.get_by_id.assert_awaited_once()
        mock_repo.delete.assert_awaited_once_with(mock_link)

    def test_task_does_nothing_when_link_missing(self):
        link_id = str(uuid.uuid4())

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        mock_repo.delete = AsyncMock()

        with patch("app.tasks.celery_app.async_session_maker") as mock_sm, \
             patch("app.tasks.celery_app.LinkRepository", return_value=mock_repo):

            mock_session = AsyncMock()
            mock_sm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sm.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.celery_app import delete_link_task
            delete_link_task(link_id)

        mock_repo.delete.assert_not_awaited()
