import uuid


def generate_uuid() -> uuid.UUID:
    """Generate a UUID (uses uuid7 if available on Python 3.13+, else uuid4)."""
    if hasattr(uuid, "uuid7"):
        return getattr(uuid, "uuid7")()
    return uuid.uuid4()


def parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    """Safely parse a string or UUID object into a UUID."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)
