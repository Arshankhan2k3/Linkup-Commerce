class CatalogError(Exception):
    """Base exception for catalog domain errors."""


class ProductNotFoundError(CatalogError):
    pass


class ProductAlreadyExistsError(CatalogError):
    pass


class InvalidProductError(CatalogError):
    pass


class VariantNotFoundError(CatalogError):
    pass


class VariantAlreadyExistsError(CatalogError):
    pass


class DuplicateSKUError(CatalogError):
    pass


class CollectionNotFoundError(CatalogError):
    pass


class CollectionAlreadyExistsError(CatalogError):
    pass


class MetafieldDefinitionNotFoundError(CatalogError):
    pass


class MetafieldValidationError(CatalogError):
    pass


class PublishProductValidationError(CatalogError):
    pass


class ConcurrencyError(CatalogError):
    pass


class MediaNotFoundError(CatalogError):
    pass


class OptionNotFoundError(CatalogError):
    pass