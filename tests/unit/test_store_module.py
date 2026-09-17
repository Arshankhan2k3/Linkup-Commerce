"""Unit tests for Store Foundation & Sales Channels module."""

from __future__ import annotations

import unittest
from uuid import uuid4

from pydantic import ValidationError

from modules.store.domain.entities import (
    ChannelStatus,
    ChannelType,
    SalesChannel,
    Store,
    StoreSettings,
    StoreStatus,
)
from modules.store.infrastructure.db.models import (
    SalesChannelModel,
    StoreModel,
    StoreSettingsModel,
)
from modules.store.presentation.http.schemas.requests import (
    SalesChannelCreateRequest,
    SalesChannelPatchRequest,
    SettingsPatchRequest,
    StorePatchRequest,
)


class TestStoreDomainEntitiesAndSchemas(unittest.TestCase):
    def test_store_domain_entity(self):
        sid = uuid4()
        store = Store(
            store_id=sid,
            name="ACME Fashion",
            country_code="IN",
            default_currency="INR",
            timezone="Asia/Kolkata",
            status=StoreStatus.ACTIVE,
        )
        self.assertEqual(store.store_id, sid)
        self.assertEqual(store.name, "ACME Fashion")
        self.assertEqual(store.country_code, "IN")
        self.assertEqual(store.default_currency, "INR")
        self.assertEqual(store.currency, "INR")
        self.assertEqual(store.status, StoreStatus.ACTIVE)

    def test_store_settings_domain_entity(self):
        setting_id = uuid4()
        store_id = uuid4()
        settings = StoreSettings(
            setting_id=setting_id,
            store_id=store_id,
            order_prefix="ACME",
            weight_unit="kg",
            dimension_unit="cm",
            tax_inclusive=True,
            allow_guest_checkout=True,
            inventory_policy="DENY",
            checkout_expiry_minutes=30,
        )
        self.assertEqual(settings.order_prefix, "ACME")
        self.assertEqual(settings.inventory_policy, "DENY")
        self.assertTrue(settings.tax_inclusive)

    def test_sales_channel_domain_entity(self):
        cid = uuid4()
        sid = uuid4()
        channel = SalesChannel(
            channel_id=cid,
            store_id=sid,
            name="Online Store",
            channel_type=ChannelType.STOREFRONT,
            status=ChannelStatus.ACTIVE,
        )
        self.assertEqual(channel.channel_id, cid)
        self.assertEqual(channel.channel_type, ChannelType.STOREFRONT)

    def test_store_patch_request_validation(self):
        # Valid patch
        req = StorePatchRequest(country_code="in", status="active")
        self.assertEqual(req.country_code, "IN")
        self.assertEqual(req.status, "ACTIVE")

        # Invalid country code length
        with self.assertRaises(ValidationError):
            StorePatchRequest(country_code="IND")

        # Invalid status
        with self.assertRaises(ValidationError):
            StorePatchRequest(status="UNKNOWN")

    def test_settings_patch_request_inventory_policy_deny_only(self):
        # Valid DENY policy
        req = SettingsPatchRequest(inventory_policy="DENY", weight_unit="kg", dimension_unit="cm")
        self.assertEqual(req.inventory_policy, "DENY")
        self.assertEqual(req.weight_unit, "kg")

        # Invalid policy (Release 1 DENY restriction)
        with self.assertRaises(ValidationError):
            SettingsPatchRequest(inventory_policy="CONTINUE")

        # Invalid weight unit
        with self.assertRaises(ValidationError):
            SettingsPatchRequest(weight_unit="pounds")

        # Invalid dimension unit
        with self.assertRaises(ValidationError):
            SettingsPatchRequest(dimension_unit="meters")

    def test_sales_channel_request_validation(self):
        # Valid channel type
        req = SalesChannelCreateRequest(name="Mobile App", channel_type="API")
        self.assertEqual(req.channel_type, "API")

        # Invalid channel type
        with self.assertRaises(ValidationError):
            SalesChannelCreateRequest(name="Mobile App", channel_type="INVALID_TYPE")

        # Valid channel patch
        patch_req = SalesChannelPatchRequest(status="inactive")
        self.assertEqual(patch_req.status, "INACTIVE")

        with self.assertRaises(ValidationError):
            SalesChannelPatchRequest(status="INVALID")


if __name__ == "__main__":
    unittest.main()
