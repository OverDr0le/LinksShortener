"""
Functional tests — POST /links/shorten

All tests use the synchronous FastAPI TestClient.  No async/await needed.
"""
from unittest.mock import patch


class TestCreateLinkAuthenticated:

    def test_create_link_returns_201(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://example.com/long-path"},
            )
        assert resp.status_code == 201

    def test_response_contains_short_url(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://example.com/path"},
            )
        body = resp.json()
        assert "short_url" in body
        assert len(body["short_url"]) > 0

    def test_response_contains_original_url(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://mysite.org/about"},
            )
        assert "mysite.org" in resp.json()["original_url"]

    def test_create_with_custom_alias(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://example.com", "custom_alias": "my-cool-link"},
            )
        assert resp.status_code == 201
        assert resp.json()["short_url"] == "my-cool-link"

    def test_duplicate_alias_returns_400(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://first.com", "custom_alias": "dup-alias"},
            )
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://second.com", "custom_alias": "dup-alias"},
            )
        assert resp.status_code == 400
        assert "уже занято" in resp.json()["detail"]

    def test_user_id_present_in_response_for_auth_user(self, authenticated_client, sample_user_id):
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://example.com/auth-user"},
            )
        assert resp.json()["user_id"] == str(sample_user_id)

    def test_response_schema_has_all_fields(self, authenticated_client):
        """Ensure the response body contains every documented field."""
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://schema-check.example.com"},
            )
        body = resp.json()
        for field in ("id", "short_url", "original_url", "user_id", "created_at", "expires_at"):
            assert field in body, f"Missing field: {field}"


class TestCreateLinkAnonymous:

    def test_anon_user_can_create_link(self, anon_client):
        with patch("app.services.link_service.delete_link_task"):
            resp = anon_client.post(
                "/links/shorten",
                json={"original_url": "https://anon.example.com"},
            )
        assert resp.status_code == 201

    def test_anon_link_has_null_user_id(self, anon_client):
        with patch("app.services.link_service.delete_link_task"):
            resp = anon_client.post(
                "/links/shorten",
                json={"original_url": "https://anon2.example.com"},
            )
        assert resp.json()["user_id"] is None

    def test_anon_link_with_expiry(self, anon_client):
        """Anonymous users can also set an expiry date."""
        with patch("app.services.link_service.delete_link_task"):
            resp = anon_client.post(
                "/links/shorten",
                json={
                    "original_url": "https://expiry-anon.example.com",
                    "expires_at": "2035-12-31T23:59:00Z",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["expires_at"] is not None


class TestCreateLinkValidation:

    def test_missing_url_returns_422(self, anon_client):
        resp = anon_client.post("/links/shorten", json={})
        assert resp.status_code == 422

    def test_invalid_url_returns_422(self, anon_client):
        resp = anon_client.post(
            "/links/shorten",
            json={"original_url": "not-a-valid-url"},
        )
        assert resp.status_code == 422

    def test_alias_too_short_returns_422(self, anon_client):
        resp = anon_client.post(
            "/links/shorten",
            json={"original_url": "https://example.com", "custom_alias": "ab"},
        )
        assert resp.status_code == 422

    def test_alias_too_long_returns_422(self, anon_client):
        resp = anon_client.post(
            "/links/shorten",
            json={"original_url": "https://example.com", "custom_alias": "x" * 51},
        )
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, anon_client):
        resp = anon_client.post("/links/shorten", json=None)
        assert resp.status_code in (422, 400)  # validation

    def test_idempotent_create_same_alias_does_not_500(self, authenticated_client):
        """Не должно быть 5xx из-за проблем с UUID/refresh в тестовой БД."""
        with patch("app.services.link_service.delete_link_task"):
            r1 = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://idem-create.com", "custom_alias": "idem-create"},
            )
            assert r1.status_code in (201, 400)

            r2 = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://idem-create.com/2", "custom_alias": "idem-create"},
            )
        assert r2.status_code in (200, 201, 400, 409, 422)
        assert r2.status_code != 500
        
