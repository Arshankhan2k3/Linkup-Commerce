from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from modules.catalog.application.dto.outputs import MediaUploadSessionDTO
from modules.catalog.application.ports.providers import IMediaStorageProvider


class LocalMediaStorageProvider(IMediaStorageProvider):
    """Media upload provider generating signed URLs and object storage keys."""

    def __init__(self, base_url: str = "https://cdn.linkup-commerce.internal") -> None:
        self.base_url = base_url

    async def generate_upload_session(
        self,
        store_id: UUID,
        media_id: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> MediaUploadSessionDTO:
        storage_key = f"stores/{store_id}/media/{media_id}/{filename}"
        upload_url = f"{self.base_url}/upload/{storage_key}?signature=signed_upload_token"
        headers = {
            "Content-Type": content_type,
            "x-amz-meta-store-id": str(store_id),
            "x-amz-meta-media-id": str(media_id),
        }
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        return MediaUploadSessionDTO(
            media_id=media_id,
            upload_url=upload_url,
            headers=headers,
            expires_at=expires_at,
        )

    async def verify_and_get_public_url(
        self,
        store_id: UUID,
        storage_key: str,
    ) -> str:
        return f"{self.base_url}/{storage_key}"
