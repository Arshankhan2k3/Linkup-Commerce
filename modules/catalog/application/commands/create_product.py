from uuid import uuid4, UUID

from modules.catalog.infrastructure.db.models import ProductModel
from modules.catalog.infrastructure.db.repositories import CatalogRepository


async def create_product(
    repository: CatalogRepository,
    store_id: UUID,
    title: str,
    slug: str,
    description_html: str | None = None,
    vendor: str | None = None,
    product_type: str | None = None,
    status: str = "DRAFT",
) -> ProductModel:

    existing = await repository.get_product_by_slug(
        store_id,
        slug,
    )

    if existing:
        raise ValueError("Product with this handle already exists")

    product = ProductModel(
        product_id=uuid4(),
        store_id=store_id,
        title=title,
        slug=slug,
        description_html=description_html,
        vendor=vendor,
        product_type=product_type,
        status=status,
    )

    return await repository.create_product(product)