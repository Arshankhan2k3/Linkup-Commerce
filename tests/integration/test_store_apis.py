"""Integration tests for Store Foundation & Sales Channels APIs."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from modules.iam.application.services.token_service import create_access_token

client = TestClient(app)


class TestStoreAPIs(unittest.TestCase):
    def setUp(self):
        self.store_id = uuid4()
        self.user_id = uuid4()

    def _create_token(self, permissions: list[str]) -> str:
        return create_access_token(
            user_id=self.user_id,
            store_id=self.store_id,
            permissions=permissions,
        )

    # 1. GET /api/v1/storefront/store
    def test_get_storefront_store_public(self):
        # Public endpoint does not require authentication
        response = client.get("/api/v1/storefront/store")
        # Should reach endpoint (returns 200 with mocked/active store or 503 if not provisioned)
        self.assertIn(response.status_code, (200, 503))

    # 2. GET /api/v1/admin/store
    def test_get_admin_store_unauthorized(self):
        response = client.get("/api/v1/admin/store")
        self.assertEqual(response.status_code, 401)

    def test_get_admin_store_forbidden_without_permission(self):
        token = self._create_token(permissions=["settings.read"])
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/admin/store", headers=headers)
        self.assertEqual(response.status_code, 403)

    # 3. PATCH /api/v1/admin/store
    def test_patch_admin_store_unauthorized(self):
        response = client.patch("/api/v1/admin/store", json={"name": "New Name"})
        self.assertEqual(response.status_code, 401)

    def test_patch_admin_store_validation_error(self):
        token = self._create_token(permissions=["store.write"])
        headers = {"Authorization": f"Bearer {token}"}
        # Invalid country code (3 letters)
        response = client.patch("/api/v1/admin/store", json={"country_code": "USA"}, headers=headers)
        self.assertEqual(response.status_code, 422)

    # 4. GET /api/v1/admin/settings
    def test_get_admin_settings_unauthorized(self):
        response = client.get("/api/v1/admin/settings")
        self.assertEqual(response.status_code, 401)

    def test_get_admin_settings_forbidden(self):
        token = self._create_token(permissions=["store.read"])
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/admin/settings", headers=headers)
        self.assertEqual(response.status_code, 403)

    # 5. PATCH /api/v1/admin/settings
    def test_patch_admin_settings_inventory_policy_validation(self):
        token = self._create_token(permissions=["settings.write"])
        headers = {"Authorization": f"Bearer {token}"}
        # Release 1 accepts inventory_policy=DENY only
        response = client.patch(
            "/api/v1/admin/settings",
            json={"inventory_policy": "CONTINUE"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 422)

    # 6. GET /api/v1/admin/sales-channels
    def test_list_sales_channels_unauthorized(self):
        response = client.get("/api/v1/admin/sales-channels")
        self.assertEqual(response.status_code, 401)

    def test_list_sales_channels_forbidden(self):
        token = self._create_token(permissions=["settings.read"])
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/admin/sales-channels", headers=headers)
        self.assertEqual(response.status_code, 403)

    # 7. POST /api/v1/admin/sales-channels
    def test_create_sales_channel_validation_error(self):
        token = self._create_token(permissions=["channels.write"])
        headers = {"Authorization": f"Bearer {token}"}
        # Invalid channel_type
        response = client.post(
            "/api/v1/admin/sales-channels",
            json={"name": "New POS", "channel_type": "INVALID"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 422)

    # 8. PATCH /api/v1/admin/sales-channels/{channel_id}
    def test_patch_sales_channel_unauthorized(self):
        cid = uuid4()
        response = client.patch(f"/api/v1/admin/sales-channels/{cid}", json={"status": "INACTIVE"})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
