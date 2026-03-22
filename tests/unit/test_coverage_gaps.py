"""
Targeted tests that cover the specific lines missing from the 88% baseline:

  • Link.__repr__ and User.__repr__
  • LinkService._cache_key
  • LinkService.get_link_service  (async-generator dependency)
  • UserManager lifecycle hooks
  • celery delete_link_task  (inner async function)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.link import Link
from app.models.user import User
from app.services.link_service import LinkService, get_link_service
from app.auth.manager import UserManager


# ── __repr__ ──────────────────────────────────────────────────────────────────

def test_link_repr_contains_key_info():
    link = Link(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        original_url="https://repr.example.com",
        short_url="repr-code",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    r = repr(link)
    assert "repr-code" in r
    assert "repr.example.com" in r


def test_user_repr_contains_email():
    user = User()
    user.id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    user.email = "repr@example.com"
    user.created_at = datetime(2025, 1, 1)
    assert "repr@example.com" in repr(user)


# ── _cache_key ────────────────────────────────────────────────────────────────

def test_cache_key_format():
    svc = LinkService(repo=AsyncMock(), redis=AsyncMock())
    assert svc._cache_key("abc123") == "short_url:abc123"


# ── get_link_service generator ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_link_service_yields_instance():
    repo, redis = AsyncMock(), AsyncMock()
    gen = get_link_service(repo=repo, redis=redis)
    svc = await gen.__anext__()
    assert isinstance(svc, LinkService)
    # exhaust generator
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass


# ── UserManager hooks ─────────────────────────────────────────────────────────

def _make_manager() -> UserManager:
    return UserManager(MagicMock())


def _make_user() -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = "hook@example.com"
    user.created_at = datetime.now()
    return user


@pytest.mark.asyncio
async def test_on_after_register(capsys):
    mgr = _make_manager()
    await mgr.on_after_register(_make_user())
    assert "зарегистрирован" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_on_after_forgot_password(capsys):
    mgr = _make_manager()
    await mgr.on_after_forgot_password(_make_user(), token="tok-reset")
    assert "tok-reset" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_on_after_request_verify(capsys):
    mgr = _make_manager()
    await mgr.on_after_request_verify(_make_user(), token="tok-verify")
    assert "tok-verify" in capsys.readouterr().out


# ── Celery delete_link_task ───────────────────────────────────────────────────

def test_delete_link_task_calls_repo_delete():
    """The inner async function must call repo.delete when the link exists."""
    link_id = str(uuid.uuid4())
    mock_link = MagicMock()

    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_link)
    mock_repo.delete = AsyncMock()

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.celery_app.async_session_maker", return_value=mock_session_cm), \
         patch("app.tasks.celery_app.LinkRepository", return_value=mock_repo):
        from app.tasks.celery_app import delete_link_task
        delete_link_task(link_id)

    mock_repo.delete.assert_awaited_once_with(mock_link)


def test_delete_link_task_noop_when_link_missing():
    """When repo returns None the task must not call delete."""
    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    mock_repo.delete = AsyncMock()

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.celery_app.async_session_maker", return_value=mock_session_cm), \
         patch("app.tasks.celery_app.LinkRepository", return_value=mock_repo):
        from app.tasks.celery_app import delete_link_task
        delete_link_task(str(uuid.uuid4()))

    mock_repo.delete.assert_not_awaited()
