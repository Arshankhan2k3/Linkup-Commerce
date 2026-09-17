from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Protocol for getting current time deterministically."""
    def now_utc(self) -> datetime: ...


class SystemClock:
    """Standard system clock returning timezone-aware UTC datetime."""
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)


default_clock = SystemClock()
