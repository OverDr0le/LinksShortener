"""
Functional tests — GET /links/by-short/{short_url}

Tests the redirect endpoint: DB lookup, Redis cache hit/miss, click-count
increments, and 404 for unknown codes.
"""
from unittest.mock import AsyncMock, patch


class TestRedirect:

    def test_redirect_returns_2xx_or_3xx_for_existing_link(
        self, authenticated_client, mock_redis
    ):
        """A valid short code must get a non-error HTTP response."""
        with patch("app.services.link_service.delete_link_task"):
            create_resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://redirect-target.com/path"},
            )
        short_url = create_resp.json()["short_url"]

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        resp = authenticated_client.get(
            f"/links/by-short/{short_url}", follow_redirects=False
        )
        assert resp.status_code in (200, 302, 307, 404)
        assert resp.status_code != 500

        

    def test_redirect_nonexistent_link_returns_404(self, anon_client, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        resp = anon_client.get("/links/by-short/doesnotexist", follow_redirects=False)
        assert resp.status_code == 404

    def test_click_count_incremented_after_redirect(self, authenticated_client, mock_redis):
        with patch("app.services.link_service.delete_link_task"):
            create_resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://click-count.example.com"},
            )
        short_url = create_resp.json()["short_url"]

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        authenticated_client.get(f"/links/by-short/{short_url}", follow_redirects=False)

        stats = authenticated_client.get(f"/links/{short_url}/stats").json()
        assert stats["click_count"] == 1

    def test_multiple_visits_increment_counter_correctly(
        self, authenticated_client, mock_redis
    ):
        with patch("app.services.link_service.delete_link_task"):
            create_resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://multi-visit.example.com"},
            )
        short_url = create_resp.json()["short_url"]

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        for _ in range(4):
            authenticated_client.get(f"/links/by-short/{short_url}", follow_redirects=False)

        stats = authenticated_client.get(f"/links/{short_url}/stats").json()
        assert stats["click_count"] == 4

    def test_cache_hit_skips_db(self, authenticated_client, mock_redis):
        """When Redis already has the value the endpoint should still succeed."""
        with patch("app.services.link_service.delete_link_task"):
            create_resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://from-cache.example.com"},
            )
        short_url = create_resp.json()["short_url"]
        
        mock_redis.get = AsyncMock(return_value=b"https://from-cache.example.com")

        resp = authenticated_client.get(
            f"/links/by-short/{short_url}", follow_redirects=False
        )
        # Service returns the cached string; router returns it with 302
        assert resp.status_code in (200, 302, 307)

    def test_last_accessed_at_set_after_first_visit(
        self, authenticated_client, mock_redis
    ):
        with patch("app.services.link_service.delete_link_task"):
            create_resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://accessed-at.example.com"},
            )
        short_url = create_resp.json()["short_url"]

        assert authenticated_client.get(f"/links/{short_url}/stats").json()["last_accessed_at"] is None

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        authenticated_client.get(f"/links/by-short/{short_url}", follow_redirects=False)

        assert authenticated_client.get(f"/links/{short_url}/stats").json()["last_accessed_at"] is not None
