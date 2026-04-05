from __future__ import annotations

from typing import Any

from src.data.chunking import build_parent_child_chunks
from src.indexing.schema import ChildChunk, ParentChunk

def build_index_records(
        doc_id:str,
        source:str,
        content:str,
        metadata : dict[str,Any] | None = None,
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    return build_parent_child_chunks(
        doc_id=doc_id,
        source=source,
        content=content,
        metadata=metadata,
    )