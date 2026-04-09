from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from src.rag.rag_chain import generate_answer
from src.retrieval.fusion import rrf_fusion
from src.retrieval.query_rewriter import rewrite_query

"""
这里可以感受到langgraph处理过程的方便之处，看起来不那么抽象，
每次到达节点只要考虑状态怎么更新就好了，相比于langchain的链式过程，可以更好地手动控制
"""

class QueryState(BaseModel):
    query: str
    owner_id: str = ""
    skip_generate: bool = False
    rewritten_query: str = ""
    rewrite_strategy: str = "identity"
    query_variants: list[str] = Field(default_factory=list)
    query_subtasks: list[str] = Field(default_factory=list)
    vector_rows: list[dict[str, Any]] = Field(default_factory=list)
    bm25_rows: list[dict[str, Any]] = Field(default_factory=list)
    fused_rows: list[dict[str, Any]] = Field(default_factory=list)
    parent_rows: list[dict[str, Any]] = Field(default_factory=list)
    answer: str = ""

def _state_update(state:QueryState,**updates:Any):
    #深拷贝创建状态
    return state.model_copy(update=updates)

def build_query_graph(settings, vector_retriever, bm25_retriever, parent_store, chat_model):
    #节点一：重写query
    def rewrite_node(state:QueryState) -> QueryState:
        rewritten = rewrite_query(
            state.query,
            chat_model,
        )
        return _state_update(
            state,
            rewritten_query = rewritten["optimized_query"],
            rewritten_strategy = rewritten["rewrite_strategy"],
            query_variants = rewritten["variants"],
            query_subtasks = rewritten["subtasks"],
        )

    #节点二：并行双路检索
    def retrieve_node(state:QueryState) -> QueryState:
        queries = state.query_variants or [state.query]
        vector_rows : list[dict[str, Any]] = []
        bm25_rows : list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=2) as pool:
            for q in queries:
                vector_future = pool.submit(
                    vector_retriever.retrieve,
                    q,
                    settings.retrieval_vector_top_k,
                    state.owner_id,
                )
                bm25_future = pool.submit(
                    bm25_retriever.retrieve,
                    q,
                    settings.retrieval_bm25_top_k,
                    state.owner_id,
                )
                vector_rows.extend(vector_future.result())
                bm25_rows.extend(bm25_future.result())

        return _state_update(
            state=state,
            vector_rows=vector_rows,
            bm25_rows=bm25_rows,
            )

    #节点三：混合
    def fusion_node(state:QueryState) -> QueryState:
        fused = rrf_fusion(
            vector_rows=state.vector_rows,
            bm25_rows=state.bm25_rows,
            vector_weight=settings.retrieval_vector_weight,
            bm25_weight=settings.retrieval_bm25_weight,
            rrf_k = settings.retrieval_rrf_k,
            dedup_by=settings.retrieval_dedup_by,
            threshold=settings.retrieval_score_threshold,
            top_k=settings.retrieval_final_top_k,
        )
        return _state_update(state=state, fused_rows=fused)

    #节点四：通过子块记录的parent_id找父块
    def expand_parent_node(state:QueryState) -> QueryState:
        fused_rows = state.fused_rows
        parent_ids = [r["parent_id"] for r in fused_rows if r.get("parent_id")]
        parent_map = parent_store.fetch_parent(parent_ids, owner_id=state.owner_id)
        blocks = []
        for row in fused_rows:
            parent = parent_map.get(row["parent_id"]) if row.get("parent_id") else None
            if row.get("parent_id") and parent is None:
                # 跳过 owner 不匹配或脏数据，避免泄漏其他用户文档。
                continue

            row_owner = str((row.get("metadata") or {}).get("owner_id", ""))
            if state.owner_id and not parent and row_owner != state.owner_id:
                continue

            blocks.append(
                {
                    "source": (parent or {}).get("source") or row.get("source", "unknown"),
                    "doc_id": (parent or {}).get("doc_id") or row.get("doc_id"),
                    "content": parent["content"] if parent else row.get("content", ""),
                    "score": row.get("score", 0.0),
                    "chunk_id": row.get("chunk_id"),
                    "parent_id": row.get("parent_id"),
                    "retrieval_source": row.get("retrieval_source", "unknown"),
                    "metadata": (parent or {}).get("metadata") or row.get("metadata") or {},
                }
            )
        return _state_update(state, parent_rows=blocks)

    #节点五：根据检索的数据生成答案
    def generate_node(state:QueryState) -> QueryState:
        if state.skip_generate:
            return state
        answer = generate_answer(
            chat_model=chat_model,
            question=state.query,
            context_blocks=state.parent_rows,
        )
        return _state_update(state, answer=answer)

    graph = StateGraph(QueryState)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("fusion", fusion_node)
    graph.add_node("expand_parent", expand_parent_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "fusion")
    graph.add_edge("fusion", "expand_parent")
    graph.add_edge("expand_parent", "generate")
    graph.add_edge("generate", END)
    return graph.compile()







