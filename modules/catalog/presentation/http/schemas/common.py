from __future__ import annotations

from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class PageInfo(BaseModel):
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None = None
    end_cursor: str | None = None


class Edge(BaseModel, Generic[T]):
    node: T
    cursor: str


class Connection(BaseModel, Generic[T]):
    edges: list[Edge[T]]
    page_info: PageInfo
    total_count: int = 0
