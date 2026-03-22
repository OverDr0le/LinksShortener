"""
Functional integration tests — full CRUD lifecycle.

Each test exercises a realistic multi-step user scenario end-to-end.
All tests are plain `def` — no async overhead needed with TestClient.
"""
from unittest.mock import AsyncMock, patch


class TestFullCrudLifecycle:

    def test_create_visit_stats_delete(self, authenticated_client, mock_redis):
        """
        Full happy-path:
          1. Create a link
          2. Visit the redirect endpoint (click count +1)
          3. Verify stats
          4. Delete the link
          5. Confirm 404
        """
        # 1. Create
        with patch("app.services.link_service.delete_link_task"):
            resp = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://lifecycle.example.com", "custom_alias": "lifecycle"},
            )
        assert resp.status_code == 201
        assert resp.json()["short_url"] == "lifecycle"

        # 2. Visit
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)
        assert authenticated_client.get(
            "/links/by-short/lifecycle", follow_redirects=False
        ).status_code in (200, 302, 307)

        # 3. Stats
        stats = authenticated_client.get("/links/lifecycle/stats").json()
        assert stats["click_count"] == 1
        assert stats["last_accessed_at"] is not None

        # 4. Delete
        assert authenticated_client.delete("/links/lifecycle").status_code == 204

        # 5. Gone
        mock_redis.get = AsyncMock(return_value=None)
        assert authenticated_client.get(
            "/links/by-short/lifecycle", follow_redirects=False
        ).status_code == 404

    def test_create_update_alias_old_link_gone(self, authenticated_client, mock_redis):
        """
        After renaming an alias:
          • old alias → 404
          • new alias → redirect works
        """
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://rename.example.com", "custom_alias": "old-name"},
            )
            update_resp = authenticated_client.put(
                "/links/old-name", json={"custom_alias": "new-name"}
            )
        assert update_resp.status_code == 200
        assert update_resp.json()["short_url"] == "new-name"

        mock_redis.get = AsyncMock(return_value=None)
        assert authenticated_client.get(
            "/links/by-short/old-name", follow_redirects=False
        ).status_code == 404
        assert authenticated_client.get(
            "/links/by-short/new-name", follow_redirects=False
        ).status_code in (200, 302, 307)

    def test_anon_create_then_auth_cannot_delete(self, anon_client, authenticated_client):
        """Anonymous link has no owner → any DELETE must 403."""
        with patch("app.services.link_service.delete_link_task"):
            assert anon_client.post(
                "/links/shorten",
                json={"original_url": "https://anon-owned.example.com", "custom_alias": "anon-owned"},
            ).status_code == 201

        # Изменено: ожидаем 403, а не 204
        resp = authenticated_client.delete("/links/anon-owned")
        assert resp.status_code == 403, f"Expected 403 but got {resp.status_code}. Response: {resp.text}"
        # Проверяем, что ссылка все еще существует
        assert anon_client.get("/links/by-short/anon-owned", follow_redirects=False).status_code != 404

    def test_multiple_links_independent(self, authenticated_client, mock_redis):
        """Two links must not interfere with each other."""
        with patch("app.services.link_service.delete_link_task"):
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://link-one.com", "custom_alias": "link-one"},
            ).status_code == 201
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://link-two.com", "custom_alias": "link-two"},
            ).status_code == 201

        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=True)

        for alias in ("link-one", "link-two"):
            assert authenticated_client.get(
                f"/links/by-short/{alias}", follow_redirects=False
            ).status_code in (200, 302, 307)

        authenticated_client.delete("/links/link-one")
        mock_redis.get = AsyncMock(return_value=None)

        assert authenticated_client.get(
            "/links/by-short/link-one", follow_redirects=False
        ).status_code == 404
        assert authenticated_client.get(
            "/links/by-short/link-two", follow_redirects=False
        ).status_code in (200, 302, 307)

    def test_search_after_create_and_update(self, authenticated_client):
        """Search by original URL must return the updated alias."""
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://search-flow.com/path", "custom_alias": "search-before"},
            )
            authenticated_client.put(
                "/links/search-before", json={"custom_alias": "search-after"}
            )

        resp = authenticated_client.get(
            "/links/by-original/search",
            params={"original_url": "https://search-flow.com/path"},
        )
        assert resp.status_code == 200
        assert resp.json()["short_url"] == "search-after"
