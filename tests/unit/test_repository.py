"""
Unit-tests for LinkRepository.
Covers every method including those not exercised by functional tests:
  • get_by_id
  • increment_click_count
  • get_by_original_url
  • create / get_by_short_url / update / delete  (smoke-level checks)

Uses the session-scoped SQLite engine from the root conftest so no
real PostgreSQL is needed.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.link import Link
from app.repositories.link_repository import LinkRepository


# ── helpers ───────────────────────────────────────────────────────────────────

def _new_link(short_url: str, user_id=None) -> Link:
    return Link(
        id=uuid.uuid4(),
        original_url=f"https://{short_url}.example.com",
        short_url=short_url,
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        expires_at=None,
        click_count=0,
        last_accessed_at=None,
    )


# ── create & get_by_short_url ─────────────────────────────────────────────────

class TestCreateAndGetByShortUrl:

    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, db_session):
        repo = LinkRepository(db_session)
        link = await repo.create(_new_link("repo-create-01"))

        found = await repo.get_by_short_url("repo-create-01")
        assert found is not None
        assert found.id == link.id

    @pytest.mark.asyncio
    async def test_get_by_short_url_returns_none_for_missing(self, db_session):
        repo = LinkRepository(db_session)
        assert await repo.get_by_short_url("totally-missing") is None


# ── get_by_id ─────────────────────────────────────────────────────────────────

class TestGetById:

    @pytest.mark.asyncio
    async def test_get_by_id_returns_correct_link(self, db_session):
        repo = LinkRepository(db_session)
        created = await repo.create(_new_link("repo-getid-01"))

        found = await repo.get_by_id(created.id)
        assert found is not None
        assert found.short_url == "repo-getid-01"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_unknown_id(self, db_session):
        repo = LinkRepository(db_session)
        assert await repo.get_by_id(uuid.uuid4()) is None


# ── get_by_original_url ───────────────────────────────────────────────────────

class TestGetByOriginalUrl:

    @pytest.mark.asyncio
    async def test_returns_link_with_matching_original_url(self, db_session):
        repo = LinkRepository(db_session)
        link = _new_link("repo-orig-01")
        link.original_url = "https://original-lookup.example.com/path"
        await repo.create(link)

        found = await repo.get_by_original_url("https://original-lookup.example.com/path")
        assert found is not None
        assert found.short_url == "repo-orig-01"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_original_url(self, db_session):
        repo = LinkRepository(db_session)
        assert await repo.get_by_original_url("https://no-match-ever.example.com") is None


# ── update ────────────────────────────────────────────────────────────────────

class TestUpdate:

    @pytest.mark.asyncio
    async def test_update_short_url(self, db_session):
        repo = LinkRepository(db_session)
        link = await repo.create(_new_link("repo-upd-before"))

        link.short_url = "repo-upd-after"
        updated = await repo.update(link)
        assert updated.short_url == "repo-upd-after"

        # Old alias must be gone
        assert await repo.get_by_short_url("repo-upd-before") is None
        assert await repo.get_by_short_url("repo-upd-after") is not None


# ── increment_click_count ─────────────────────────────────────────────────────

class TestIncrementClickCount:
    """
    LinkRepository.increment_click_count executes a bulk UPDATE — it is a
    separate DB method not called by LinkService (which instead uses
    repo.update after setting link.click_count manually).  We test it here
    to ensure full repository coverage.
    """

    @pytest.mark.asyncio
    async def test_increments_by_one(self, db_session):
        repo = LinkRepository(db_session)
        link = await repo.create(_new_link("repo-click-01"))
        assert link.click_count == 0

        link.last_accessed_at = datetime.now(timezone.utc)
        await repo.increment_click_count(link)

        refreshed = await repo.get_by_short_url("repo-click-01")
        assert refreshed.click_count == 1



# ── delete ────────────────────────────────────────────────────────────────────

class TestDelete:

    @pytest.mark.asyncio
    async def test_delete_removes_link(self, db_session):
        repo = LinkRepository(db_session)
        link = await repo.create(_new_link("repo-del-01"))

        await repo.delete(link)
        assert await repo.get_by_short_url("repo-del-01") is None
