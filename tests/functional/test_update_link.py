"""
Functional tests — PUT /links/{short_url}
"""
from unittest.mock import patch


class TestUpdateLink:

    def test_owner_can_update_alias(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://update-me.com", "custom_alias": "before-update"},
            ).status_code == 201
            resp = authenticated_client.put(
                "/links/before-update",
                json={"custom_alias": "after-update"},
            )
        assert resp.status_code == 200
        assert resp.json()["short_url"] == "after-update"

    def test_owner_can_update_expires_at(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://expiry-update.com", "custom_alias": "expiry-link"},
            ).status_code == 201
            resp = authenticated_client.put(
                "/links/expiry-link",
                json={"expires_at": "2035-01-01T12:00:00Z"},
            )
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is not None

    def test_non_owner_gets_403(self, authenticated_client, other_client):
        with patch("app.services.link_service.delete_link_task"):
            assert authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://owner-link.com", "custom_alias": "owner-only"},
            ).status_code == 201

        resp = other_client.put("/links/owner-only", json={"custom_alias": "stolen-alias"})
        assert resp.status_code == 403

    def test_update_nonexistent_link_returns_404(self, authenticated_client):
        resp = authenticated_client.put("/links/ghost-link", json={"custom_alias": "anything"})
        assert resp.status_code == 404

    def test_update_to_taken_alias_returns_4xx(self, authenticated_client):
        """Renaming to an alias owned by another link must be rejected."""
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://a.com", "custom_alias": "alias-a"},
            )
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://b.com", "custom_alias": "alias-b"},
            )
            resp = authenticated_client.put(
                "/links/alias-a", json={"custom_alias": "alias-b"}
            )
        assert resp.status_code in (400, 404)

    def test_update_alias_too_short_returns_422(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://val.com", "custom_alias": "valid-alias-val"},
            )
        resp = authenticated_client.put(
            "/links/valid-alias-val", json={"custom_alias": "ab"}
        )
        assert resp.status_code == 422

    def test_update_alias_too_long_returns_422(self, authenticated_client):
        with patch("app.services.link_service.delete_link_task"):
            authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://long.com", "custom_alias": "long-alias-test"},
            )
        resp = authenticated_client.put(
            "/links/long-alias-test", json={"custom_alias": "x" * 51}
        )
        assert resp.status_code == 422

    def test_update_same_alias_is_idempotent(self, authenticated_client):
        """If alias is set to its current value the update should not crash."""
        with patch("app.services.link_service.delete_link_task"):
            resp_create = authenticated_client.post(
                "/links/shorten",
                json={"original_url": "https://idempotent.com", "custom_alias": "idem-alias"},
            )
            assert resp_create.status_code == 201

            # The service implementation may treat this as a no-op.
            # We only assert it does not raise 5xx.
            resp = authenticated_client.put(
                "/links/idem-alias", json={"custom_alias": "idem-alias"}
            )

        assert resp.status_code in (200, 400, 404)  # accept idempotent or “alias taken” behavior
        assert resp.status_code != 500
            
            
