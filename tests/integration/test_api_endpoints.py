"""Integration tests for IAM and Customers API endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAPIEndpoints(unittest.TestCase):
    def test_iam_login_validation_error(self):
        # Sending empty body to POST /api/v1/auth/login should return 422 Unprocessable Entity
        response = client.post("/api/v1/auth/login", json={})
        self.assertEqual(response.status_code, 422)

    def test_iam_refresh_validation_error(self):
        response = client.post("/api/v1/auth/refresh", json={})
        self.assertEqual(response.status_code, 422)

    def test_customer_register_validation_error(self):
        response = client.post("/api/v1/storefront/customers/register", json={})
        self.assertEqual(response.status_code, 422)

    def test_customer_login_validation_error(self):
        response = client.post("/api/v1/storefront/customers/login", json={})
        self.assertEqual(response.status_code, 422)

    def test_admin_staff_unauthorized(self):
        # Protected route without token should return 401
        response = client.get("/api/v1/admin/staff")
        self.assertEqual(response.status_code, 401)

    def test_admin_roles_unauthorized(self):
        response = client.get("/api/v1/admin/roles")
        self.assertEqual(response.status_code, 401)

    def test_admin_customers_unauthorized(self):
        response = client.get("/api/v1/admin/customers")
        self.assertEqual(response.status_code, 401)

    def test_customer_me_unauthorized(self):
        response = client.get("/api/v1/storefront/customers/me")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
