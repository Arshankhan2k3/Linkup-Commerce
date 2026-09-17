"""Unit tests for IAM and Customers modules."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from modules.iam.application.services.token_service import (
    create_access_token,
    create_customer_access_token,
    decode_access_token,
)
from modules.iam.infrastructure.db.models import (
    PermissionModel,
    RefreshTokenModel,
    RoleModel,
    StaffMemberModel,
    UserModel,
)
from modules.customers.infrastructure.db.models import (
    CustomerAddressModel,
    CustomerConsentModel,
    CustomerModel,
    CustomerNoteModel,
)


class TestIAMModelsAndTokens(unittest.TestCase):
    def test_token_service(self):
        user_id = uuid4()
        store_id = uuid4()
        permissions = ["products.read", "products.write"]

        # Staff token test
        token = create_access_token(
            user_id=user_id,
            store_id=store_id,
            permissions=permissions,
        )
        payload = decode_access_token(token)

        self.assertEqual(payload["sub"], str(user_id))
        self.assertEqual(payload["store_id"], str(store_id))
        self.assertEqual(payload["permissions"], permissions)
        self.assertEqual(payload["role"], "staff")

        # Customer token test
        customer_id = uuid4()
        c_token = create_customer_access_token(
            customer_id=customer_id,
            store_id=store_id,
        )
        c_payload = decode_access_token(c_token)

        self.assertEqual(c_payload["sub"], str(customer_id))
        self.assertEqual(c_payload["store_id"], str(store_id))
        self.assertEqual(c_payload["role"], "customer")

    def test_user_model_attributes(self):
        u = UserModel(
            user_id=uuid4(),
            email="test@merchant.com",
            password_hash="hashed_secret",
            status="ACTIVE",
        )
        self.assertEqual(u.status, "ACTIVE")
        self.assertEqual(u.email, "test@merchant.com")

    def test_customer_model_attributes(self):
        c = CustomerModel(
            customer_id=uuid4(),
            store_id=uuid4(),
            email="buyer@example.com",
            status="ACTIVE",
            accepts_marketing=True,
        )
        self.assertEqual(c.status, "ACTIVE")
        self.assertTrue(c.accepts_marketing)

    def test_customer_address_model_attributes(self):
        addr = CustomerAddressModel(
            address_id=uuid4(),
            customer_id=uuid4(),
            line1="123 Main St",
            city="New York",
            state="NY",
            postal_code="10001",
            country_code="US",
            is_default=True,
        )
        self.assertEqual(addr.line1, "123 Main St")
        self.assertTrue(addr.is_default)

    def test_customer_consent_model_attributes(self):
        consent = CustomerConsentModel(
            consent_id=uuid4(),
            customer_id=uuid4(),
            channel="EMAIL",
            purpose="MARKETING",
            state="SUBSCRIBED",
        )
        self.assertEqual(consent.channel, "EMAIL")
        self.assertEqual(consent.state, "SUBSCRIBED")


if __name__ == "__main__":
    unittest.main()
