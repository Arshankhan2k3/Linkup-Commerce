from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from modules.catalog.application.dto.inputs import CreateCollectionInput, UpdateCollectionInput
from modules.catalog.application.dto.outputs import CollectionDTO
from modules.catalog.domain.enums import CollectionStatus, CollectionType
from modules.catalog.domain.events import CollectionUpdated
from modules.catalog.domain.exceptions import CollectionAlreadyExistsError, CollectionNotFoundError
from modules.catalog.domain.services import PureDomainCatalogService
from modules.catalog.infrastructure.db.models import CollectionModel, CollectionProductModel
from modules.catalog.infrastructure.db.repositories import CatalogRepository


def _collection_model_to_dto(model: CollectionModel) -> CollectionDTO:
    return CollectionDTO(
        collection_id=model.collection_id,
        store_id=model.store_id,
        title=model.title,
        slug=model.slug,
        description_html=model.description_html,
        collection_type=model.collection_type,
        rule_json=model.rule_json,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


async def execute_create_collection(
    repository: CatalogRepository,
    input_dto: CreateCollectionInput,
) -> CollectionDTO:
    slug = input_dto.slug or PureDomainCatalogService.slugify(input_dto.title)
    existing = await repository.get_collection_by_slug(input_dto.store_id, slug)
    if existing:
        raise CollectionAlreadyExistsError(f"Collection with handle '{slug}' already exists")

    collection_id = uuid4()
    model = CollectionModel(
        collection_id=collection_id,
        store_id=input_dto.store_id,
        title=input_dto.title,
        slug=slug,
        description_html=input_dto.description_html,
        collection_type=input_dto.collection_type or CollectionType.MANUAL.value,
        rule_json=input_dto.rule_json,
        status=input_dto.status or CollectionStatus.ACTIVE.value,
    )

    created = await repository.create_collection(model)
    return _collection_model_to_dto(created)


async def execute_update_collection(
    repository: CatalogRepository,
    input_dto: UpdateCollectionInput,
) -> tuple[CollectionDTO, CollectionUpdated]:
    collection = await repository.get_collection(input_dto.store_id, input_dto.collection_id)
    if not collection:
        raise CollectionNotFoundError(f"Collection '{input_dto.collection_id}' not found")

    values: dict = {}
    if input_dto.title is not None:
        values["title"] = input_dto.title
    if input_dto.slug is not None:
        slug = PureDomainCatalogService.slugify(input_dto.slug)
        existing = await repository.get_collection_by_slug(input_dto.store_id, slug)
        if existing and existing.collection_id != input_dto.collection_id:
            raise CollectionAlreadyExistsError(f"Collection with handle '{slug}' already exists")
        values["slug"] = slug
    if input_dto.description_html is not None:
        values["description_html"] = input_dto.description_html
    if input_dto.status is not None:
        values["status"] = input_dto.status
    if input_dto.rule_json is not None:
        values["rule_json"] = input_dto.rule_json

    values["updated_at"] = datetime.now(timezone.utc)

    updated = await repository.update_collection(input_dto.store_id, input_dto.collection_id, values)
    if not updated:
        raise CollectionNotFoundError(f"Collection '{input_dto.collection_id}' not found")

    event = CollectionUpdated(collection_id=updated.collection_id, store_id=updated.store_id)
    return _collection_model_to_dto(updated), event


async def execute_replace_collection_products(
    repository: CatalogRepository,
    store_id: UUID,
    collection_id: UUID,
    product_ids: list[UUID],
) -> list[UUID]:
    collection = await repository.get_collection(store_id, collection_id)
    if not collection:
        raise CollectionNotFoundError(f"Collection '{collection_id}' not found")

    await repository.delete_collection_products(collection_id)

    for idx, pid in enumerate(product_ids):
        cp = CollectionProductModel(
            collection_id=collection_id,
            product_id=pid,
            position=idx,
        )
        await repository.add_collection_product(cp)

    return product_ids
