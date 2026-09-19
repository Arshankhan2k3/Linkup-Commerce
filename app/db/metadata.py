"""Database metadata registry.

Import all ORM models here so SQLAlchemy's MetaData object is fully
populated before Alembic or ``Base.metadata.create_all()`` is called.

Every new module that adds ORM models MUST register an import here.
"""

from __future__ import annotations

# Core base (must be imported first)
from app.db.base import Base  # noqa: F401

# ---- Store ---------------------------------------------------------------
# Import triggers model class registration on Base.metadata
from modules.store.infrastructure.db.models import (  # noqa: F401
    StoreModel,
    StoreSettingsModel,
    SalesChannelModel,
)

# ---- IAM -----------------------------------------------------------------
from modules.iam.infrastructure.db.models import (  # noqa: F401
    UserModel,
    RoleModel,
    PermissionModel,
    RolePermissionModel,
    StaffMemberModel,
    StaffMemberRoleModel,
    RefreshTokenModel,
)

# ---- Customers -----------------------------------------------------------
from modules.customers.infrastructure.db.models import (  # noqa: F401
    CustomerModel,
    CustomerAddressModel,
    CustomerConsentModel,
    CustomerNoteModel,
)

# ---- Catalog --------------------------------------------------------------
from modules.catalog.infrastructure.db.models import (
    ProductModel,
    ProductOptionModel,
    ProductOptionValueModel,
    ProductVariantModel,
    VariantOptionValueModel,
    MediaAssetModel,
    ProductMediaModel,
    CollectionModel,
    CollectionProductModel,
    TagModel,
    ProductTagModel,
    MetafieldDefinitionModel,
    MetafieldModel,
)

__all__ = ["Base"]