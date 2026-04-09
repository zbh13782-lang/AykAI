from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    doc_id : str = Field(...,min_length=1)
    source : str = Field(default="manual")
    content:str = Field(...,min_length=1)
    metadata:dict[str, Any] = Field(default_factory=dict)

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    stream: bool = False
