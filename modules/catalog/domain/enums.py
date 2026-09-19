from enum import Enum


class ProductStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class CollectionType(str, Enum):
    MANUAL = "MANUAL"
    SMART = "SMART"


class CollectionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"


class InventoryPolicy(str, Enum):
    DENY = "DENY"
    CONTINUE = "CONTINUE"


class MediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    FILE = "FILE"


class MetafieldOwnerType(str, Enum):
    PRODUCT = "PRODUCT"
    VARIANT = "VARIANT"
    CUSTOMER = "CUSTOMER"
    ORDER = "ORDER"


class MetafieldValueType(str, Enum):
    TEXT = "text"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    JSON = "json"
    URL = "url"

