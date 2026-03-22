"""
Unit-tests for LinkService._normalize_expires_at
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest

from app.services.link_service import LinkService


def _make_service() -> LinkService:
    return LinkService(repo=AsyncMock(), redis=AsyncMock())


class TestNormalizeExpiresAt:

    def test_none_returns_none(self):
        svc = _make_service()
        assert svc._normalize_expires_at(None) is None

    def test_naive_datetime_gets_utc(self):
        svc = _make_service()
        naive = datetime(2025, 6, 15, 12, 30, 45, 123456)   # no tzinfo
        result = svc._normalize_expires_at(naive)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_seconds_and_microseconds_stripped(self):
        svc = _make_service()
        dt = datetime(2025, 6, 15, 12, 30, 59, 999999, tzinfo=timezone.utc)
        result = svc._normalize_expires_at(dt)
        assert result.second == 0
        assert result.microsecond == 0

    def test_minute_precision_preserved(self):
        svc = _make_service()
        dt = datetime(2025, 6, 15, 12, 30, 0, 0, tzinfo=timezone.utc)
        result = svc._normalize_expires_at(dt)
        assert result.hour == 12
        assert result.minute == 30

    def test_non_utc_timezone_converted_to_utc(self):
        """A datetime in UTC+3 must be shifted back to UTC."""
        svc = _make_service()
        utc_plus_3 = timezone(timedelta(hours=3))
        dt = datetime(2025, 6, 15, 15, 0, 0, tzinfo=utc_plus_3)   # 15:00 +3 == 12:00 UTC
        result = svc._normalize_expires_at(dt)
        assert result.tzinfo == timezone.utc
        assert result.hour == 12

    def test_already_utc_unchanged_except_precision(self):
        svc = _make_service()
        dt = datetime(2025, 6, 15, 10, 45, 33, 777, tzinfo=timezone.utc)
        result = svc._normalize_expires_at(dt)
        assert result.hour == 10
        assert result.minute == 45
        assert result.second == 0
        assert result.microsecond == 0
