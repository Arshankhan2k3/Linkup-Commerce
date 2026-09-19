from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from modules.catalog.application.dto.inputs import CreateMetafieldDefinitionInput, MetafieldItemInput
from modules.catalog.application.dto.outputs import MetafieldDefinitionDTO, MetafieldDTO
from modules.catalog.domain.exceptions import MetafieldDefinitionNotFoundError
from modules.catalog.domain.policies import MetafieldValidationPolicy
from modules.catalog.infrastructure.db.models import MetafieldDefinitionModel, MetafieldModel
from modules.catalog.infrastructure.db.repositories import CatalogRepository


def _def_model_to_dto(model: MetafieldDefinitionModel) -> MetafieldDefinitionDTO:
    return MetafieldDefinitionDTO(
        definition_id=model.definition_id,
        store_id=model.store_id,
        resource_type=model.resource_type,
        namespace=model.namespace,
        key=model.key,
        value_type=model.value_type,
        validation=model.validation,
        created_at=model.created_at,
    )


async def execute_create_metafield_definition(
    repository: CatalogRepository,
    input_dto: CreateMetafieldDefinitionInput,
) -> MetafieldDefinitionDTO:
    def_id = uuid4()
    model = MetafieldDefinitionModel(
        definition_id=def_id,
        store_id=input_dto.store_id,
        resource_type=input_dto.resource_type.upper(),
        namespace=input_dto.namespace.lower(),
        key=input_dto.key.lower(),
        value_type=input_dto.value_type.lower(),
        validation=input_dto.validation or {},
    )

    created = await repository.create_metafield_definition(model)
    return _def_model_to_dto(created)


async def execute_upsert_metafields(
    repository: CatalogRepository,
    store_id: UUID,
    resource_type: str,
    resource_id: UUID,
    items: list[MetafieldItemInput],
) -> list[MetafieldDTO]:
    res_type_norm = resource_type.upper()
    dtos: list[MetafieldDTO] = []

    for item in items:
        definition = await repository.get_metafield_definition(store_id, item.definition_id)
        if not definition or definition.resource_type != res_type_norm:
            raise MetafieldDefinitionNotFoundError(
                f"Metafield definition '{item.definition_id}' not found for resource type '{res_type_norm}'"
            )

        # Validate value via domain policy
        from modules.catalog.domain.entities import MetafieldDefinition as DomainDef
        d_def = DomainDef(
            definition_id=definition.definition_id,
            store_id=definition.store_id,
            resource_type=definition.resource_type,
            namespace=definition.namespace,
            key=definition.key,
            value_type=definition.value_type,
            validation=definition.validation,
        )
        validated_val = MetafieldValidationPolicy.validate_value(d_def, item.value)

        existing = await repository.get_metafield(item.definition_id, resource_id)
        if existing:
            updated = await repository.update_metafield(
                item.definition_id,
                resource_id,
                {"value_json": {"value": validated_val}, "updated_at": datetime.now(timezone.utc)},
            )
            model = updated
        else:
            metafield_id = uuid4()
            mf_model = MetafieldModel(
                metafield_id=metafield_id,
                definition_id=item.definition_id,
                resource_type=res_type_norm,
                resource_id=resource_id,
                value_json={"value": validated_val},
            )
            model = await repository.create_metafield(mf_model)

        dtos.append(
            MetafieldDTO(
                metafield_id=model.metafield_id,
                definition_id=model.definition_id,
                resource_type=model.resource_type,
                resource_id=model.resource_id,
                value_json=model.value_json.get("value") if isinstance(model.value_json, dict) and "value" in model.value_json else model.value_json,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
        )

    return dtos
