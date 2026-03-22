"""
Unit-tests for LinkService._generate_short_code
"""
import string
from unittest.mock import AsyncMock

from app.services.link_service import LinkService

ALLOWED_CHARS = set(string.ascii_letters + string.digits)


def _make_service() -> LinkService:
    return LinkService(repo=AsyncMock(), redis=AsyncMock())


class TestGenerateShortCode:

    def test_default_length_is_six(self):
        assert len(_make_service()._generate_short_code()) == 6

    def test_custom_length_respected(self):
        assert len(_make_service()._generate_short_code(length=10)) == 10

    def test_only_url_safe_characters(self):
        svc = _make_service()
        for _ in range(50):
            assert not (set(svc._generate_short_code()) - ALLOWED_CHARS)

    def test_uniqueness(self):
        svc = _make_service()
        codes = {svc._generate_short_code() for _ in range(50)}
        assert len(codes) == 50
