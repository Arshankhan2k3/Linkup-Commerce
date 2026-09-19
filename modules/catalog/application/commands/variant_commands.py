from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from modules.catalog.application.dto.inputs import (
    BulkVariantItemInput,
    CreateOptionInput,
    CreateVariantInput,
    UpdateOptionInput,
    UpdateVariantInput,
)
from modules.catalog.application.dto.outputs import OptionDTO, OptionValueDTO, VariantDTO
from modules.catalog.domain.events import VariantCreated, VariantUpdated
from modules.catalog.domain.exceptions import (
    ConcurrencyError,
    DuplicateSKUError,
    InvalidProductError,
    ProductNotFoundError,
    VariantAlreadyExistsError,
    VariantNotFoundError,
)
from modules.catalog.domain.value_objects import OptionSignature
from modules.catalog.infrastructure.db.models import (
    ProductOptionModel,
    ProductOptionValueModel,
    ProductVariantModel,
    VariantOptionValueModel,
)
from modules.catalog.infrastructure.db.repositories import CatalogRepository


def _variant_model_to_dto(model: ProductVariantModel, option_value_ids: list[UUID] | None = None) -> VariantDTO:
    return VariantDTO(
        variant_id=model.variant_id,
        store_id=model.store_id,
        product_id=model.product_id,
        option_signature=model.option_signature,
        base_price=model.base_price,
        currency=model.currency,
        sku=model.sku,
        barcode=model.barcode,
        title=model.title,
        compare_at_price=model.compare_at_price,
        cost_price=model.cost_price,
        weight=float(model.weight) if model.weight is not None else None,
        weight_unit=model.weight_unit,
        length=float(model.length) if model.length is not None else None,
        width=float(model.width) if model.width is not None else None,
        height=float(model.height) if model.height is not None else None,
        dimension_unit=model.dimension_unit,
        position=model.position,
        inventory_policy=model.inventory_policy,
        is_active=model.is_active,
        version=model.version,
        option_value_ids=option_value_ids or [],
    )


async def execute_create_option(
    repository: CatalogRepository,
    input_dto: CreateOptionInput,
) -> OptionDTO:
    option_id = uuid4()
    option = ProductOptionModel(
        option_id=option_id,
        product_id=input_dto.product_id,
        name=input_dto.name,
        position=input_dto.position,
    )
    created_option = await repository.create_option(option)

    val_dtos: list[OptionValueDTO] = []
    for idx, val_in in enumerate(input_dto.values):
        val_id = uuid4()
        val_model = ProductOptionValueModel(
            option_value_id=val_id,
            option_id=created_option.option_id,
            value=val_in.value,
            position=val_in.position or idx,
            metadata_json=val_in.metadata or {},
        )
        created_val = await repository.create_option_value(val_model)
        val_dtos.append(
            OptionValueDTO(
                option_value_id=created_val.option_value_id,
                option_id=created_val.option_id,
                value=created_val.value,
                position=created_val.position,
                metadata=created_val.metadata_json,
            )
        )

    return OptionDTO(
        option_id=created_option.option_id,
        product_id=created_option.product_id,
        name=created_option.name,
        position=created_option.position,
        values=val_dtos,
    )


async def execute_update_option(
    repository: CatalogRepository,
    input_dto: UpdateOptionInput,
) -> OptionDTO:
    option = await repository.get_option(input_dto.product_id, input_dto.option_id)
    if not option:
        raise InvalidProductError(f"Option '{input_dto.option_id}' not found for product")

    values: dict = {}
    if input_dto.name is not None:
        values["name"] = input_dto.name
    if input_dto.position is not None:
        values["position"] = input_dto.position

    if values:
        option = await repository.update_option(input_dto.product_id, input_dto.option_id, values)

    val_models = await repository.list_option_values(input_dto.option_id)
    val_dtos = [
        OptionValueDTO(
            option_value_id=v.option_value_id,
            option_id=v.option_id,
            value=v.value,
            position=v.position,
            metadata=v.metadata_json,
        )
        for v in val_models
    ]

    return OptionDTO(
        option_id=option.option_id,
        product_id=option.product_id,
        name=option.name,
        position=option.position,
        values=val_dtos,
    )


async def execute_create_variant(
    repository: CatalogRepository,
    input_dto: CreateVariantInput,
) -> tuple[VariantDTO, VariantCreated]:
    product = await repository.get_product(input_dto.store_id, input_dto.product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{input_dto.product_id}' not found")

    if input_dto.sku:
        existing_sku = await repository.get_variant_by_sku(input_dto.store_id, input_dto.sku)
        if existing_sku:
            raise DuplicateSKUError(f"Variant with SKU '{input_dto.sku}' already exists in store")

    signature_vo = OptionSignature.generate(input_dto.option_value_ids)
    sig_str = signature_vo.signature

    existing_sig = await repository.get_variant_by_signature(input_dto.product_id, sig_str)
    if existing_sig:
        raise VariantAlreadyExistsError(f"Variant with option signature '{sig_str}' already exists for this product")

    variant_id = uuid4()
    variant = ProductVariantModel(
        variant_id=variant_id,
        store_id=input_dto.store_id,
        product_id=input_dto.product_id,
        sku=input_dto.sku,
        barcode=input_dto.barcode,
        option_signature=sig_str,
        title=input_dto.title,
        base_price=input_dto.base_price,
        compare_at_price=input_dto.compare_at_price,
        cost_price=input_dto.cost_price,
        currency=input_dto.currency or "USD",
        weight=input_dto.weight,
        weight_unit=input_dto.weight_unit,
        length=input_dto.length,
        width=input_dto.width,
        height=input_dto.height,
        dimension_unit=input_dto.dimension_unit,
        is_active=input_dto.is_active,
    )

    created_variant = await repository.create_variant(variant)

    for val_id in input_dto.option_value_ids:
        vov = VariantOptionValueModel(
            variant_id=created_variant.variant_id,
            option_value_id=val_id,
        )
        await repository.add_variant_option_value(vov)

    event = VariantCreated(
        variant_id=created_variant.variant_id,
        product_id=created_variant.product_id,
        store_id=created_variant.store_id,
        sku=created_variant.sku,
    )
    return _variant_model_to_dto(created_variant, input_dto.option_value_ids), event


async def execute_update_variant(
    repository: CatalogRepository,
    input_dto: UpdateVariantInput,
) -> tuple[VariantDTO, VariantUpdated]:
    variant = await repository.get_variant(input_dto.store_id, input_dto.variant_id)
    if not variant:
        raise VariantNotFoundError(f"Variant '{input_dto.variant_id}' not found")

    if input_dto.version is not None and variant.version != input_dto.version:
        raise ConcurrencyError("Variant has been modified by another transaction")

    if input_dto.sku and input_dto.sku != variant.sku:
        existing_sku = await repository.get_variant_by_sku(input_dto.store_id, input_dto.sku)
        if existing_sku and existing_sku.variant_id != input_dto.variant_id:
            raise DuplicateSKUError(f"Variant with SKU '{input_dto.sku}' already exists in store")

    values: dict = {}
    if input_dto.sku is not None:
        values["sku"] = input_dto.sku
    if input_dto.barcode is not None:
        values["barcode"] = input_dto.barcode
    if input_dto.base_price is not None:
        values["base_price"] = input_dto.base_price
    if input_dto.compare_at_price is not None:
        values["compare_at_price"] = input_dto.compare_at_price
    if input_dto.cost_price is not None:
        values["cost_price"] = input_dto.cost_price
    if input_dto.weight is not None:
        values["weight"] = input_dto.weight
    if input_dto.weight_unit is not None:
        values["weight_unit"] = input_dto.weight_unit
    if input_dto.length is not None:
        values["length"] = input_dto.length
    if input_dto.width is not None:
        values["width"] = input_dto.width
    if input_dto.height is not None:
        values["height"] = input_dto.height
    if input_dto.dimension_unit is not None:
        values["dimension_unit"] = input_dto.dimension_unit
    if input_dto.is_active is not None:
        values["is_active"] = input_dto.is_active

    values["version"] = variant.version + 1
    values["updated_at"] = datetime.now(timezone.utc)

    updated = await repository.update_variant(input_dto.store_id, input_dto.variant_id, values)
    if not updated:
        raise VariantNotFoundError(f"Variant '{input_dto.variant_id}' not found")

    opt_vals = await repository.list_variant_option_values(updated.variant_id)
    opt_val_ids = [ov.option_value_id for ov in opt_vals]

    event = VariantUpdated(
        variant_id=updated.variant_id,
        product_id=updated.product_id,
        store_id=updated.store_id,
    )
    return _variant_model_to_dto(updated, opt_val_ids), event


async def execute_bulk_variants(
    repository: CatalogRepository,
    store_id: UUID,
    product_id: UUID,
    items: list[BulkVariantItemInput],
) -> list[VariantDTO]:
    if len(items) > 100:
        raise InvalidProductError("Bulk variant operations cannot exceed 100 items per request")

    results: list[VariantDTO] = []
    for item in items:
        if item.variant_id:
            up_input = UpdateVariantInput(
                store_id=store_id,
                variant_id=item.variant_id,
                sku=item.sku,
                barcode=item.barcode,
                base_price=item.base_price,
                compare_at_price=item.compare_at_price,
                is_active=item.is_active,
            )
            dto, _ = await execute_update_variant(repository, up_input)
            results.append(dto)
        else:
            cr_input = CreateVariantInput(
                store_id=store_id,
                product_id=product_id,
                base_price=item.base_price,
                sku=item.sku,
                barcode=item.barcode,
                option_value_ids=item.option_value_ids,
                compare_at_price=item.compare_at_price,
                is_active=item.is_active,
            )
            dto, _ = await execute_create_variant(repository, cr_input)
            results.append(dto)
    return results
