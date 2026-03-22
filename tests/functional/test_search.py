"""
Functional tests — GET /links/by-original/search
"""
from unittest.mock import patch


class TestSearchByOriginalUrl:

    def test_search_returns_200_for_existing_url(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://search-target.com/path", "custom_alias": "search-alias"},
            )

        resp = authenticated_client.get(
            "/links/by-original/search",
            params={"original_url": "https://search-target.com/path"},
        )
        assert resp.status_code == 200

    def test_search_response_contains_short_url(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://resp-check.com", "custom_alias": "resp-check"},
            )

        body = authenticated_client.get(
            "/links/by-original/search",
            params={"original_url": "https://resp-check.com"},
        ).json()
        assert body["short_url"] == "resp-check"

    def test_search_response_contains_original_url(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://orig-in-resp.com/page", "custom_alias": "orig-resp"},
            )

        body = authenticated_client.get(
            "/links/by-original/search",
            params={"original_url": "https://orig-in-resp.com/page"},
        ).json()
        assert "orig-in-resp.com" in body["original_url"]

    def test_search_returns_404_for_unknown_url(self, anon_client):
        resp = anon_client.get(
            "/links/by-original/search",
            params={"original_url": "https://does-not-exist-anywhere.com"},
        )
        assert resp.status_code == 404

    def test_search_without_query_param_returns_422(self, anon_client):
        assert anon_client.get("/links/by-original/search").status_code == 422

    def test_search_accessible_without_auth(self, anon_client, authenticated_client):
        """Проверяем, что поиск работает без авторизации."""
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://anon-search.com", "custom_alias": "anon-search"},
            )

        resp = anon_client.get(
            "/links/by-original/search",
            params={"original_url": "https://anon-search.com"},
        )
        assert resp.status_code == 200

    def test_search_exact_match_required(self, anon_client, authenticated_client):
        """A partial URL must NOT match the full stored URL."""
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://exact-match.com/full/path", "custom_alias": "exact-link"},
            )

        resp = anon_client.get(
            "/links/by-original/search",
            params={"original_url": "https://exact-match.com"},
        )
        assert resp.status_code == 404
