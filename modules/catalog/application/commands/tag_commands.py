from __future__ import annotations

from uuid import UUID, uuid4

from modules.catalog.application.dto.outputs import TagDTO
from modules.catalog.domain.exceptions import ProductNotFoundError
from modules.catalog.domain.services import PureDomainCatalogService
from modules.catalog.infrastructure.db.models import ProductTagModel, TagModel
from modules.catalog.infrastructure.db.repositories import CatalogRepository


async def execute_replace_product_tags(
    repository: CatalogRepository,
    store_id: UUID,
    product_id: UUID,
    tag_names: list[str],
) -> list[TagDTO]:
    product = await repository.get_product(store_id, product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    await repository.delete_product_tags(product_id)

    tag_dtos: list[TagDTO] = []
    seen = set()

    for raw_name in tag_names:
        norm = PureDomainCatalogService.normalize_tag(raw_name)
        if not norm or norm.lower() in seen:
            continue
        seen.add(norm.lower())

        tag = await repository.get_tag(store_id, norm)
        if not tag:
            tag = TagModel(
                tag_id=uuid4(),
                store_id=store_id,
                name=norm,
            )
            tag = await repository.create_tag(tag)

        pt = ProductTagModel(
            product_id=product_id,
            tag_id=tag.tag_id,
        )
        await repository.add_product_tag(pt)
        tag_dtos.append(TagDTO(tag_id=tag.tag_id, store_id=tag.store_id, name=tag.name))

    return tag_dtos
