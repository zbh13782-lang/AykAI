from dataclasses import dataclass, field
from typing import Any

@dataclass
class ParentChunk:
    parent_id: str
    doc_id: str
    content: str
    source: str
    child_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChildChunk:
    chunk_id: str
    parent_id: str
    doc_id: str
    content: str
    source: str
    chunk_order: int
    metadata: dict[str, Any] = field(default_factory=dict)
