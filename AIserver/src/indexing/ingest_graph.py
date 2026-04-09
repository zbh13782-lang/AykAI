from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import START, END, StateGraph
from pydantic import BaseModel,Field
from pathlib import Path
from src.indexing.parent_child_builder import build_index_records
import json

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
    inserted_children: int = 0      #已插入子块数量
    inserted_parents: int = 0     #已插入父块数量


def build_ingest_graph(
        embeddings,
        milvus_service,
        parent_store,
        semantic_indexer = None,
        bm25_indexer = None,
        write_retry_attempts: int = 3,
        ):

    #错误重试机制
    def _run_with_retries(func,rows:list[dict[str, Any]],stage:str) -> None:
        last_exc = Exception | None
        attempts = max(1,int(write_retry_attempts))
        for _ in range(attempts):
            try:
                func(rows)
                return
            except Exception as e:
                last_exc = e
        raise RuntimeError(f"ingest write failed at stage={stage}: {last_exc}") from last_exc

    def _enqueue_repair(stage:str,child_rows:list[dict[str, Any]],parent_rows:list[dict[str,Any]]) -> None:
        repair_path = Path("logs/ingest_repair_queue.jsonl")
        repair_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "stage": stage,
            "parent_rows": parent_rows,
            "child_rows": [{k: v for k, v in row.items() if k != "embedding"} for row in child_rows],
        }
        with repair_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")


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


        try:
            _run_with_retries(milvus_service.upsert_children,child_rows,stage = "metadata")
            if semantic_indexer is not None and getattr(semantic_indexer, "enabled", False):
                _run_with_retries(semantic_indexer.upsert_children, child_rows, stage="elasticsearch")
            _run_with_retries(parent_store.upsert_parents, parent_rows, stage="postgres")
            if bm25_indexer is not None:
                bm25_indexer.upsert_children(child_rows)
        except Exception as e:
            _enqueue_repair(stage = 'upsert',child_rows=child_rows,parent_rows=parent_rows)
            raise e


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


