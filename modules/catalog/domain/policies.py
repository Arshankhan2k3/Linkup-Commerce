from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from .entities import MetafieldDefinition, Product, ProductVariant
from .enums import MetafieldValueType, ProductStatus
from .exceptions import MetafieldValidationError, PublishProductValidationError


class ProductPublishPolicy:
    @staticmethod
    def validate_for_publishing(product: Product, variants: list[ProductVariant]) -> None:
        if not product.title or not product.title.strip():
            raise PublishProductValidationError("Product title cannot be empty")

        active_sellable_variants = [
            v for v in variants if v.is_active and v.base_price > Decimal("0")
        ]
        if not active_sellable_variants:
            raise PublishProductValidationError(
                "Cannot publish product: product requires at least one active variant with a valid base_price > 0"
            )


class MetafieldValidationPolicy:
    """Validates custom metafield values against their definition rules."""

    @staticmethod
    def validate_value(definition: MetafieldDefinition, value: Any) -> Any:
        value_type = definition.value_type

        if value is None:
            raise MetafieldValidationError(f"Metafield value cannot be None for key '{definition.key}'")

        if value_type == MetafieldValueType.TEXT:
            if not isinstance(value, str):
                raise MetafieldValidationError(f"Expected text value for key '{definition.key}'")
            return value

        elif value_type == MetafieldValueType.INTEGER:
            try:
                int_val = int(value)
                return int_val
            except (ValueError, TypeError):
                raise MetafieldValidationError(f"Expected integer value for key '{definition.key}'")

        elif value_type == MetafieldValueType.BOOLEAN:
            if not isinstance(value, bool):
                if str(value).lower() in ("true", "1"):
                    return True
                elif str(value).lower() in ("false", "0"):
                    return False
                raise MetafieldValidationError(f"Expected boolean value for key '{definition.key}'")
            return value

        elif value_type == MetafieldValueType.URL:
            if not isinstance(value, str):
                raise MetafieldValidationError(f"Expected URL string for key '{definition.key}'")
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise MetafieldValidationError(f"Invalid URL format for key '{definition.key}'")
            return value

        elif value_type == MetafieldValueType.JSON:
            if isinstance(value, (dict, list)):
                return value
            elif isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    raise MetafieldValidationError(f"Invalid JSON string for key '{definition.key}'")
            raise MetafieldValidationError(f"Expected JSON payload for key '{definition.key}'")

        return value
