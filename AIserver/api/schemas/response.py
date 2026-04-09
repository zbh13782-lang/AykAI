from typing import Any

from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str
    app:str

class IngestResponse(BaseModel):
    status: str
    inserted_parents: int
    inserted_children: int

class ReferenceItem(BaseModel):
    source: str
    doc_id: str | None = None
    chunk_id: str | None = None
    parent_id: str | None = None
    score: float = 0.0
    retrieval_source: str = "unknown"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class QueryResponse(BaseModel):
    status: str
    answer: str
    references: list[ReferenceItem]
