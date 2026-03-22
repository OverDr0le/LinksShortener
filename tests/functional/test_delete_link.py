"""
Functional tests — DELETE /links/{short_url}
"""
from unittest.mock import AsyncMock, patch


class TestDeleteLink:

    def test_owner_can_delete_link(self, authenticated_client):
        # idempotent-ish delete behavior: must not crash with 5xx
        
        with patch("app.services.link_service.delete_link_task"):
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://delete-me.com", "custom_alias": "del-link"},
            ).status_code == 201

        assert authenticated_client.delete("/links/del-link").status_code == 204

    def test_deleted_link_no_longer_accessible(self, authenticated_client, mock_redis):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://gone.com", "custom_alias": "gone-link"},
            )
        authenticated_client.delete("/links/gone-link")

        mock_redis.get = AsyncMock(return_value=None)
        resp = authenticated_client.get("/links/by-short/gone-link", follow_redirects=False)
        assert resp.status_code == 404

    def test_non_owner_cannot_delete(self, authenticated_client, other_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://protected.com", "custom_alias": "protected-del"},
            )

        # Changed: ожидаем 403, а не 204
        resp = other_client.delete("/links/protected-del")
        assert resp.status_code == 403, f"Expected 403 but got {resp.status_code}. Response: {resp.text}"
        # Проверяем, что ссылка все еще существует
        assert authenticated_client.get("/links/by-short/protected-del", follow_redirects=False).status_code != 404

    def test_delete_nonexistent_link_returns_404(self, authenticated_client):
        assert authenticated_client.delete("/links/ghost-del").status_code == 404

    def test_anon_link_cannot_be_deleted_by_any_user(
        self, anon_client, authenticated_client
    ):
        """Links without an owner must be undeletable (403)."""
        with patch("app.services.link_service.delete_link_task"):
            assert anon_client.post(
                "/links/shorten",
                json={"original_url": "https://anon-del.com", "custom_alias": "anon-del-link"},
            ).status_code == 201

        # Изменено: ожидаем 403, а не 204
        resp = authenticated_client.delete("/links/anon-del-link")
        assert resp.status_code == 403, f"Expected 403 but got {resp.status_code}. Response: {resp.text}"
        # Проверяем, что ссылка все еще существует
        assert anon_client.get("/links/by-short/anon-del-link", follow_redirects=False).status_code != 404

    def test_double_delete_returns_404(self, authenticated_client):
        """Second DELETE on the same code must 404, not 500."""
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://double-del.com", "custom_alias": "double-del"},
            )
        authenticated_client.delete("/links/double-del")
        assert authenticated_client.delete("/links/double-del").status_code == 404
