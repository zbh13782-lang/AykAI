from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import START, END, StateGraph
from pydantic import BaseModel,Field

from src.indexing.parent_child_builder import build_index_records

#数据处理管道
#chunk->embed->upsert


class IngestState(BaseModel):

    doc_id: str
    source: str = "unknown"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parents: list[dict[str, Any]] = Field(default_factory=list)
    children: list[dict[str, Any]] = Field(default_factory=list)
    child_embeddings: list[list[float]] = Field(default_factory=list)
    inserted_children: int = 0
    inserted_parents: int = 0     #已插入父块数量

def _bm25_row_key(row: dict[str, Any]) -> tuple[str, str]:
    # 为索引生成唯一建，保证快照幂等性
    return (str(row.get("doc_id", "")), str(row.get("content", "")))

def build_ingest_graph(embeddings,milvus_service,metadata_store,parent_store):

    #节点1：chunk_node  文档分块
    def chunk_node(state:IngestState) -> IngestState:
        parents, children = build_index_records(
            doc_id=state.doc_id,
            source=state.source,
            content=state.content,
            metadata=state.metadata,
        )
        return state.model_copy(
            update={
                "parents": [p.__dict__ for p in parents],
                "children": [c.__dict__ for c in children],
            }
        )

    #节点2：embed_node 向量化
    def embed_node(state:IngestState) -> IngestState:
        texts = [c["content"] for c in state.children]
        vectors = embeddings.embed_documents(texts)
        return state.model_copy(update={"child_embeddings": vectors})

    #节点3:upsert_node 入库
    def upsert_node(state:IngestState) -> IngestState:
        if len(state.children) != len(state.child_embeddings):
            raise ValueError(
                f"children/embeddings length mismatch: {len(state.children)} != {len(state.child_embeddings)}"
            )

        parent_rows = [
            {
                "parent_id": p["parent_id"],
                "doc_id": p["doc_id"],
                "source": p["source"],
                "content": p["content"],
                "metadata": p.get("metadata", {}),
            }
            for p in state.parents
        ]
        child_rows = []
        bm25_rows = []
        for c, vec in zip(state.children, state.child_embeddings, strict=False):
            child_rows.append(
                {
                    "chunk_id": c["chunk_id"],
                    "parent_id": c["parent_id"],
                    "doc_id": c["doc_id"],
                    "source": c["source"],
                    "chunk_order": c["chunk_order"],
                    "content": c["content"],
                    "metadata": c.get("metadata", {}),
                    "embedding": vec,
                }
            )
            bm25_rows.append(
                {
                    "chunk_id": c["chunk_id"],
                    "parent_id": c["parent_id"],
                    "doc_id": c["doc_id"],
                    "source": c["source"],
                    "content": c["content"],
                    "metadata": c.get("metadata", {}),
                }
            )

        parent_store.upsert_parents(parent_rows)
        milvus_service.upsert_children(child_rows)

        existing = metadata_store.load_bm25_docs()

        merged_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in existing:
            merged_by_key[_bm25_row_key(row)] = row
        for row in bm25_rows:
            merged_by_key[_bm25_row_key(row)] = row
        metadata_store.save_bm25_docs(list(merged_by_key.values()))

        return state.model_copy(
            update={
                "inserted_parents": len(parent_rows),
                "inserted_children": len(child_rows),
            }
        )

    graph = StateGraph(IngestState)
    graph.add_node("chunk", chunk_node)
    graph.add_node("embed", embed_node)
    graph.add_node("upsert", upsert_node)

    graph.add_edge(START, "chunk")
    graph.add_edge("chunk", "embed")
    graph.add_edge("embed", "upsert")
    graph.add_edge("upsert", END)
    return graph.compile()


