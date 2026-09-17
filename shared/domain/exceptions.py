class DomainError(Exception):
    """Base exception for all domain business errors."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class EntityNotFoundError(DomainError):
    """Raised when an aggregate or entity cannot be found."""
    def __init__(self, entity_name: str, entity_id: str | None = None):
        msg = f"{entity_name} not found" if entity_id is None else f"{entity_name} with id {entity_id} not found"
        super().__init__(message=msg, code="RESOURCE_NOT_FOUND")
        self.entity_name = entity_name
        self.entity_id = entity_id


class InvariantViolationError(DomainError):
    """Raised when a business invariant is violated."""
    def __init__(self, message: str, code: str = "INVARIANT_VIOLATION"):
        super().__init__(message=message, code=code)


class DuplicateResourceError(DomainError):
    """Raised when a unique constraint would be violated."""
    def __init__(self, message: str, code: str = "DUPLICATE_RESOURCE"):
        super().__init__(message=message, code=code)


class UnauthorizedActionError(DomainError):
    """Raised when an action is not authorized in domain context."""
    def __init__(self, message: str = "Action not permitted", code: str = "PERMISSION_DENIED"):
        super().__init__(message=message, code=code)


class ConcurrencyError(DomainError):
    """Raised when an optimistic lock / version conflict occurs."""
    def __init__(self, message: str = "Resource has been modified concurrently", code: str = "VERSION_CONFLICT"):
        super().__init__(message=message, code=code)
