from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.catalog.application.dto.outputs import MediaUploadSessionDTO


class IMediaStorageProvider(Protocol):
    """Port for object storage / CDN media uploads."""

    async def generate_upload_session(
        self,
        store_id: UUID,
        media_id: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> MediaUploadSessionDTO:
        ...
        
    async def verify_and_get_public_url(
        self,
        store_id: UUID,
        storage_key: str,
    ) -> str:
        ...
