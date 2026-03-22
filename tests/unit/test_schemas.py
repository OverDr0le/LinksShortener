"""
Unit-tests for Pydantic schemas (validation logic).
No I/O — pure model instantiation and field-validation checks.
"""

import pytest
from pydantic import ValidationError

from app.schemas.link import LinkCreate, LinkUpdate
from app.schemas.user import UserCreate


# ── LinkCreate ────────────────────────────────────────────────────────────────

class TestLinkCreate:

    def test_valid_url_accepted(self):
        lc = LinkCreate(original_url="https://example.com")
        assert str(lc.original_url).startswith("https://")

    def test_invalid_url_rejected(self):
        with pytest.raises(ValidationError):
            LinkCreate(original_url="not-a-url")

    def test_custom_alias_min_length(self):
        with pytest.raises(ValidationError):
            LinkCreate(original_url="https://example.com", custom_alias="ab")   # 2 chars

    def test_custom_alias_max_length(self):
        with pytest.raises(ValidationError):
            LinkCreate(original_url="https://example.com", custom_alias="x" * 51)

    def test_custom_alias_valid(self):
        lc = LinkCreate(original_url="https://example.com", custom_alias="valid-alias")
        assert lc.custom_alias == "valid-alias"

    def test_optional_fields_default_to_none(self):
        lc = LinkCreate(original_url="https://example.com")
        assert lc.custom_alias is None
        assert lc.expires_at is None


# ── LinkUpdate ────────────────────────────────────────────────────────────────

class TestLinkUpdate:

    def test_all_fields_optional(self):
        lu = LinkUpdate()
        assert lu.custom_alias is None
        assert lu.expires_at is None

    def test_alias_too_short(self):
        with pytest.raises(ValidationError):
            LinkUpdate(custom_alias="xy")

    def test_alias_too_long(self):
        with pytest.raises(ValidationError):
            LinkUpdate(custom_alias="a" * 51)

    def test_valid_update(self):
        lu = LinkUpdate(custom_alias="new-slug")
        assert lu.custom_alias == "new-slug"


# ── UserCreate password validation ───────────────────────────────────────────

class TestUserCreatePassword:

    def test_valid_password(self):
        uc = UserCreate(email="test@example.com", password="StrongPass1")
        assert uc.password == "StrongPass1"

    def test_no_uppercase_rejected(self):
        with pytest.raises(ValidationError, match="заглавную букву"):
            UserCreate(email="test@example.com", password="weakpass1")

    def test_no_lowercase_rejected(self):
        with pytest.raises(ValidationError, match="строчную букву"):
            UserCreate(email="test@example.com", password="STRONGPASS1")

    def test_no_digit_rejected(self):
        with pytest.raises(ValidationError, match="цифру"):
            UserCreate(email="test@example.com", password="NoDigitsHere")

    def test_too_short_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="Sh0rt")

    def test_too_long_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="A1" + "b" * 50)
