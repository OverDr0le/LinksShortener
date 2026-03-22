"""
Unit-tests for the core business logic inside LinkService.
All external I/O (DB, Redis, Celery) is mocked.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.link import Link
from app.schemas.link import LinkCreate, LinkUpdate
from app.services.link_service import LinkService


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_link(
    short_url="abc123",
    original_url="https://example.com",
    user_id=None,
    click_count=0,
) -> Link:
    return Link(
        id=uuid.uuid4(),
        original_url=original_url,
        short_url=short_url,
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        expires_at=None,
        click_count=click_count,
        last_accessed_at=None,
    )


def _make_service(repo=None, redis=None) -> LinkService:
    repo = repo or AsyncMock()
    redis = redis or AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return LinkService(repo=repo, redis=redis)


# ── create_link ───────────────────────────────────────────────────────────────

class TestCreateLink:

    @pytest.mark.asyncio
    async def test_creates_link_with_custom_alias(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        link_obj = _make_link(short_url="my-alias", original_url="https://example.com")
        repo.create = AsyncMock(return_value=link_obj)

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com", custom_alias="my-alias")

        with patch("app.services.link_service.delete_link_task"):
            result = await svc.create_link(data)

        assert result.short_url == "my-alias"
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_if_alias_taken(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=_make_link("my-alias"))

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com", custom_alias="my-alias")

        with pytest.raises(ValueError, match="уже занято"):
            await svc.create_link(data)

    @pytest.mark.asyncio
    async def test_auto_generates_short_code(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        link_obj = _make_link()
        repo.create = AsyncMock(return_value=link_obj)

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com")

        with patch("app.services.link_service.delete_link_task"):
            result = await svc.create_link(data)

        assert result is not None
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_runtime_after_max_attempts(self):
        """If every generated code is already taken, RuntimeError must be raised."""
        repo = AsyncMock()
        # Always return "taken"
        repo.get_by_short_url = AsyncMock(return_value=_make_link())

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com")

        with pytest.raises(RuntimeError, match="уникальный короткий код"):
            await svc.create_link(data, max_attempts=3)

    @pytest.mark.asyncio
    async def test_schedules_celery_task_when_expires_at_set(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        expires = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
        link_obj = _make_link()
        link_obj.expires_at = expires
        repo.create = AsyncMock(return_value=link_obj)

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com", expires_at=expires)

        with patch("app.services.link_service.delete_link_task") as mock_task:
            await svc.create_link(data)
            mock_task.apply_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_celery_task_when_no_expiry(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        link_obj = _make_link()
        link_obj.expires_at = None
        repo.create = AsyncMock(return_value=link_obj)

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com")

        with patch("app.services.link_service.delete_link_task") as mock_task:
            await svc.create_link(data)
            mock_task.apply_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_user_id_stored_on_link(self):
        uid = uuid.uuid4()
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        created_link = _make_link(user_id=uid)
        repo.create = AsyncMock(return_value=created_link)

        svc = _make_service(repo=repo)
        data = LinkCreate(original_url="https://example.com")

        with patch("app.services.link_service.delete_link_task"):
            result = await svc.create_link(data, user_id=uid)

        assert result.user_id == uid


# ── get_link (cache logic) ────────────────────────────────────────────────────

class TestGetLink:

    @pytest.mark.asyncio
    async def test_returns_cached_url(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"https://cached.example.com")
        redis.set = AsyncMock()

        repo = AsyncMock()
        svc = LinkService(repo=repo, redis=redis)

        result = await svc.get_link("abc123")

        assert result == b"https://cached.example.com"
        repo.get_by_short_url.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_queries_db_on_cache_miss_and_caches(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()

        link = _make_link(short_url="abc123", original_url="https://db.example.com")
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)

        svc = LinkService(repo=repo, redis=redis)
        result = await svc.get_link("abc123")

        assert result == "https://db.example.com"
        redis.set.assert_awaited_once()  # value was cached

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)

        svc = LinkService(repo=repo, redis=redis)
        result = await svc.get_link("notexist")

        assert result is None


# ── update_link ───────────────────────────────────────────────────────────────

class TestUpdateLink:

    @pytest.mark.asyncio
    async def test_raises_if_link_not_found(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        svc = _make_service(repo=repo)

        with pytest.raises(ValueError, match="не найдена"):
            await svc.update_link("nocode", LinkUpdate(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_permission_if_no_owner(self):
        link = _make_link(user_id=None)
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        svc = _make_service(repo=repo)

        with pytest.raises(PermissionError, match="Незарегистрированные"):
            await svc.update_link("abc123", LinkUpdate(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_permission_if_wrong_owner(self):
        link = _make_link(user_id=uuid.uuid4())
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        svc = _make_service(repo=repo)

        with pytest.raises(PermissionError, match="собственные"):
            await svc.update_link("abc123", LinkUpdate(), uuid.uuid4())   # different user

    @pytest.mark.asyncio
    async def test_updates_alias_and_refreshes_cache(self):
        uid = uuid.uuid4()
        link = _make_link(short_url="old-alias", user_id=uid)
        updated = _make_link(short_url="new-alias", user_id=uid)

        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        # new alias is not taken
        repo.get_by_short_url = AsyncMock(side_effect=lambda s: link if s == "old-alias" else None)
        repo.update = AsyncMock(return_value=updated)

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.delete = AsyncMock()

        svc = LinkService(repo=repo, redis=redis)
        data = LinkUpdate(custom_alias="new-alias")

        with patch("app.services.link_service.delete_link_task"):
            result = await svc.update_link("old-alias", data, uid)

        redis.delete.assert_awaited_once_with("short_url:old-alias")
        redis.set.assert_awaited_once()
        assert result.short_url == "new-alias"

    @pytest.mark.asyncio
    async def test_raises_if_new_alias_already_taken_by_another_link(self):
        uid = uuid.uuid4()
        link = _make_link(short_url="old", user_id=uid)
        other = _make_link(short_url="taken")  # different link owns "taken"

        repo = AsyncMock()

        async def _get_by_short(s):
            if s == "old":
                return link
            if s == "taken":
                return other
            return None

        repo.get_by_short_url = AsyncMock(side_effect=_get_by_short)
        svc = _make_service(repo=repo)

        with pytest.raises(ValueError, match="уже занято"):
            await svc.update_link("old", LinkUpdate(custom_alias="taken"), uid)


# ── delete_link ───────────────────────────────────────────────────────────────

class TestDeleteLink:

    @pytest.mark.asyncio
    async def test_raises_if_link_not_found(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        svc = _make_service(repo=repo)

        with pytest.raises(ValueError, match="не найдена"):
            await svc.delete_link("nocode", uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_permission_if_no_owner(self):
        link = _make_link(user_id=None)
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        svc = _make_service(repo=repo)

        with pytest.raises(PermissionError, match="Незарегистрированные"):
            await svc.delete_link("abc123", uuid.uuid4())

    @pytest.mark.asyncio
    async def test_raises_permission_if_wrong_owner(self):
        link = _make_link(user_id=uuid.uuid4())
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        svc = _make_service(repo=repo)

        with pytest.raises(PermissionError, match="собственные"):
            await svc.delete_link("abc123", uuid.uuid4())

    @pytest.mark.asyncio
    async def test_deletes_link_and_removes_from_cache(self):
        uid = uuid.uuid4()
        link = _make_link(short_url="del-me", user_id=uid)
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        repo.delete = AsyncMock()

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()

        svc = LinkService(repo=repo, redis=redis)
        await svc.delete_link("del-me", uid)

        repo.delete.assert_awaited_once_with(link)
        redis.delete.assert_awaited_once_with("short_url:del-me")


# ── increment_click ───────────────────────────────────────────────────────────

class TestIncrementClick:

    @pytest.mark.asyncio
    async def test_increments_counter(self):
        link = _make_link(click_count=5)
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        repo.update = AsyncMock(return_value=link)

        svc = _make_service(repo=repo)
        await svc.increment_click("abc123")

        assert link.click_count == 6
        repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_last_accessed_at(self):
        link = _make_link()
        assert link.last_accessed_at is None

        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        repo.update = AsyncMock(return_value=link)

        svc = _make_service(repo=repo)
        await svc.increment_click("abc123")

        assert link.last_accessed_at is not None

    @pytest.mark.asyncio
    async def test_raises_if_link_not_found(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        svc = _make_service(repo=repo)

        with pytest.raises(ValueError, match="не найдена"):
            await svc.increment_click("ghost")


# ── get_stats ─────────────────────────────────────────────────────────────────

class TestGetStats:

    @pytest.mark.asyncio
    async def test_returns_stats_for_existing_link(self):
        link = _make_link(click_count=42)
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=link)
        svc = _make_service(repo=repo)

        stats = await svc.get_stats("abc123")
        assert stats.click_count == 42

    @pytest.mark.asyncio
    async def test_raises_if_not_found(self):
        repo = AsyncMock()
        repo.get_by_short_url = AsyncMock(return_value=None)
        svc = _make_service(repo=repo)

        with pytest.raises(ValueError, match="не найдена"):
            await svc.get_stats("ghost")


# ── to_response ───────────────────────────────────────────────────────────────

class TestToResponse:

    @pytest.mark.asyncio
    async def test_maps_fields_correctly(self):
        uid = uuid.uuid4()
        link = _make_link(short_url="xyz", original_url="https://map.test", user_id=uid)

        svc = _make_service()
        resp = await svc.to_response(link)

        assert str(resp.original_url).rstrip("/") == "https://map.test"
        assert resp.short_url == "xyz"
        assert resp.user_id == uid
