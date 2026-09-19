from __future__ import annotations

from uuid import UUID, uuid4

from modules.catalog.application.dto.inputs import (
    CompleteMediaInput,
    CreateMediaSessionInput,
    ProductMediaItemInput,
)
from modules.catalog.application.dto.outputs import (
    MediaAssetDTO,
    MediaUploadSessionDTO,
    ProductMediaDTO,
)
from modules.catalog.application.ports.providers import IMediaStorageProvider
from modules.catalog.domain.enums import MediaType
from modules.catalog.domain.events import MediaReady
from modules.catalog.domain.exceptions import MediaNotFoundError, ProductNotFoundError
from modules.catalog.infrastructure.db.models import MediaAssetModel, ProductMediaModel
from modules.catalog.infrastructure.db.repositories import CatalogRepository


async def execute_create_media_session(
    repository: CatalogRepository,
    media_provider: IMediaStorageProvider,
    input_dto: CreateMediaSessionInput,
) -> MediaUploadSessionDTO:
    media_id = uuid4()
    storage_key = f"stores/{input_dto.store_id}/media/{media_id}/{input_dto.filename}"

    # Standard public URL layout
    public_url = f"https://cdn.linkup-commerce.internal/{storage_key}"

    m_type = MediaType.FILE.value
    if input_dto.content_type.startswith("image/"):
        m_type = MediaType.IMAGE.value
    elif input_dto.content_type.startswith("video/"):
        m_type = MediaType.VIDEO.value

    media_model = MediaAssetModel(
        media_id=media_id,
        store_id=input_dto.store_id,
        media_type=m_type,
        storage_key=storage_key,
        public_url=public_url,
        mime_type=input_dto.content_type,
        size_bytes=input_dto.size_bytes,
    )
    await repository.create_media(media_model)

    return await media_provider.generate_upload_session(
        store_id=input_dto.store_id,
        media_id=media_id,
        filename=input_dto.filename,
        content_type=input_dto.content_type,
        size_bytes=input_dto.size_bytes,
    )


async def execute_complete_media(
    repository: CatalogRepository,
    input_dto: CompleteMediaInput,
) -> tuple[MediaAssetDTO, MediaReady]:
    media = await repository.get_media(input_dto.store_id, input_dto.media_id)
    if not media:
        raise MediaNotFoundError(f"Media asset '{input_dto.media_id}' not found")

    values: dict = {}
    if input_dto.width is not None:
        values["width"] = input_dto.width
    if input_dto.height is not None:
        values["height"] = input_dto.height

    updated = await repository.update_media(input_dto.store_id, input_dto.media_id, values)
    if not updated:
        raise MediaNotFoundError(f"Media asset '{input_dto.media_id}' not found")

    dto = MediaAssetDTO(
        media_id=updated.media_id,
        store_id=updated.store_id,
        media_type=updated.media_type,
        storage_key=updated.storage_key,
        public_url=updated.public_url,
        alt_text=updated.alt_text,
        mime_type=updated.mime_type,
        width=updated.width,
        height=updated.height,
        size_bytes=updated.size_bytes,
        created_at=updated.created_at,
    )
    event = MediaReady(media_id=updated.media_id, store_id=updated.store_id)
    return dto, event


async def execute_replace_product_media(
    repository: CatalogRepository,
    store_id: UUID,
    product_id: UUID,
    items: list[ProductMediaItemInput],
) -> list[ProductMediaDTO]:
    product = await repository.get_product(store_id, product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    await repository.delete_product_media(product_id)

    dtos: list[ProductMediaDTO] = []
    for item in items:
        media_asset = await repository.get_media(store_id, item.media_id)
        if not media_asset:
            raise MediaNotFoundError(f"Media '{item.media_id}' does not belong to store")

        pm_id = uuid4()
        pm_model = ProductMediaModel(
            product_media_id=pm_id,
            product_id=product_id,
            media_id=item.media_id,
            variant_id=item.variant_id,
            position=item.position,
            is_primary=item.is_primary,
        )
        created = await repository.add_product_media(pm_model)
        dtos.append(
            ProductMediaDTO(
                product_media_id=created.product_media_id,
                product_id=created.product_id,
                media_id=created.media_id,
                variant_id=created.variant_id,
                position=created.position,
                is_primary=created.is_primary,
                public_url=media_asset.public_url,
            )
        )
    return dtos
