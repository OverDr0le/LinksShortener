"""
Functional tests — GET /links/{short_url}/stats
"""
from unittest.mock import AsyncMock, patch


class TestGetStats:

    def test_stats_returns_200_for_existing_link(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://stats-test.com", "custom_alias": "stats-link"},
            ).status_code == 201

        assert authenticated_client.get("/links/stats-link/stats").status_code == 200

    def test_stats_contains_required_fields(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://stats-fields.com", "custom_alias": "stats-fields"},
            )

        body = authenticated_client.get("/links/stats-fields/stats").json()
        for field in ("id", "short_url", "original_url", "click_count",
                      "created_at", "expires_at", "last_accessed_at", "user_id"):
            assert field in body, f"Missing field: {field}"

    def test_stats_initial_click_count_is_zero(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://zero-clicks.com", "custom_alias": "zero-clicks"},
            )

        assert authenticated_client.get("/links/zero-clicks/stats").json()["click_count"] == 0

    def test_stats_click_count_increments_correctly(self, authenticated_client, mock_redis):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://count-me.com", "custom_alias": "count-me"},
            )

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        for _ in range(3):
            authenticated_client.get("/links/by-short/count-me", follow_redirects=False)

        assert authenticated_client.get("/links/count-me/stats").json()["click_count"] == 3

    def test_stats_last_accessed_at_set_after_visit(self, authenticated_client, mock_redis):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://accessed.com", "custom_alias": "accessed-link"},
            )

        assert authenticated_client.get("/links/accessed-link/stats").json()["last_accessed_at"] is None

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        authenticated_client.get("/links/by-short/accessed-link", follow_redirects=False)

        assert authenticated_client.get("/links/accessed-link/stats").json()["last_accessed_at"] is not None

    def test_stats_returns_404_for_missing_link(self, authenticated_client):
        assert authenticated_client.get("/links/no-such-link/stats").status_code == 404

    def test_stats_accessible_without_auth(self, anon_client, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://public-stats.com", "custom_alias": "pub-stats"},
            )

        assert anon_client.get("/links/pub-stats/stats").status_code == 200

    def test_stats_expiry_reflected(self, authenticated_client):
        """expires_at in stats must match the value set at creation time."""
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={
                    "original_url": "https://expiry-stats.com",
                    "custom_alias": "expiry-stats",
                    "expires_at": "2035-06-15T10:00:00Z",
                },
            )

        body = authenticated_client.get("/links/expiry-stats/stats").json()
        assert body["expires_at"] is not None
        assert "2035" in body["expires_at"]
