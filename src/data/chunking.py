import uuid
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.indexing.schema import ChildChunk, ParentChunk


def build_parent_child_chunks(
        doc_id:str,
        source:str,
        content:str,
        metadata:dict[str, Any] | None = None,
        parent_chunk_size: int  = 1600,
        parent_overlap:int = 120,
        child_chunk_size: int = 400,
        child_overlap: int = 60,
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    metadata = metadata or {}
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size = parent_chunk_size,
        chunk_overlap = parent_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )

    parent_texts = parent_splitter.split_text(content)
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []

    for parent_idx,ptxt in enumerate(parent_texts):
        parent_id = f"p-{uuid.uuid4().hex}"
        child_texts = child_splitter.split_text(ptxt)
        child_ids : list[str] = []

        for child_idx,ctxt in enumerate(child_texts):
            chunk_id = chunk_id = f"{doc_id}-c-{parent_idx}-{child_idx}-{uuid.uuid4().hex[:8]}"
            child_ids.append(chunk_id)
            children.append(
                ChildChunk(
                    chunk_id=chunk_id,
                    parent_id=parent_id,
                    doc_id=doc_id,
                    content=ctxt,
                    source=source,
                    chunk_order=child_idx,
                    metadata=metadata,
                )
            )

        parents.append(
            ParentChunk(
                parent_id=parent_id,
                doc_id=doc_id,
                content=ptxt,
                source=source,
                child_ids=child_ids,
                metadata=metadata,
            )
        )

    return parents, children