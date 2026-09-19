from __future__ import annotations

import re
from uuid import UUID

from .entities import ProductOption, ProductOptionValue
from .exceptions import InvalidProductError


class PureDomainCatalogService:
    """Pure domain service containing stateless catalog business logic."""

    @staticmethod
    def slugify(text: str) -> str:
        """Normalize string to URL handle/slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-")

    @staticmethod
    def normalize_tag(name: str) -> str:
        """Normalize tag name (strip whitespace, retain title casing or clean string)."""
        return name.strip()

    @staticmethod
    def validate_option_combination(
        options: list[ProductOption],
        option_values: list[ProductOptionValue],
        selected_value_ids: list[UUID],
    ) -> None:
        """Ensure each option contributes at most one value, and all value IDs exist."""
        val_map = {val.option_value_id: val.option_id for val in option_values}
        selected_option_ids = set()

        for vid in selected_value_ids:
            if vid not in val_map:
                raise InvalidProductError(f"Option value ID '{vid}' does not belong to this product")
            opt_id = val_map[vid]
            if opt_id in selected_option_ids:
                raise InvalidProductError(f"Multiple values selected for option ID '{opt_id}'")
            selected_option_ids.add(opt_id)
