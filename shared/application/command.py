from typing import Generic, Protocol, TypeVar

C = TypeVar("C")
R = TypeVar("R")


class Command(Protocol):
    """Marker protocol for commands."""
    pass


class CommandHandler(Protocol, Generic[C, R]):
    """Protocol for executing a command."""
    async def handle(self, command: C) -> R: ...
