from __future__ import annotations

from typing import Any, Mapping

from langgraph.graph import START,END, StateGraph
from pydantic import BaseModel, Field

from config.settings import Settings
from retrieval.bm25_retriever import BM25Retriever
from retrieval.vector_retriever import VectorRetriever
from src.rag.rag_chain import generate_answer
from src.retrieval.fusion import weighted_fusion

'''用户查询 → 向量检索 → BM25检索 → 融合 → 扩展父文档 → 生成答案 → 返回答案'''

class QueryState(BaseModel):
    query: str
    skip_generate:bool = False      #是否跳过生成步骤
    vector_rows:list[dict[str,Any]] = Field(default_factory=list)
    bm25_rows:list[dict[str,Any]] = Field(default_factory=list)
    fused_rows:list[dict[str,Any]] = Field(default_factory=list)
    parent_rows:list[dict[str,Any]] = Field(default_factory=list)
    answer:str = ''

def _state_update(state:QueryState,**updates:Any):
    #深拷贝创建状态
    return state.model_copy(update=updates)

def build_query_graph(settings:Settings,vector_retriever:VectorRetriever,bm25_retriever:BM25Retriever,parent_store,chat_model):

    def vector_node(state:QueryState) -> QueryState:
        vector_rows = vector_retriever.retrieve(state.query,settings.retrieval_vector_top_k)
        return _state_update(state=state,vector_rows=vector_rows)

    def bm25_node(state:QueryState) -> QueryState:
        bm25_rows = bm25_retriever.retrieve(state.query,settings.retrieval_bm25_top_k)
        return _state_update(state=state,bm25_rows=bm25_rows)

    def fusion_node(state:QueryState) -> QueryState:
        fusion_rows = weighted_fusion(
            state.vector_rows,
            state.bm25_rows,
            settings.retrieval_vector_weight,
            settings.retrieval_bm25_weight,
            settings.retrieval_dedup_by,
            settings.retrieval_score_threshold,
            settings.retrieval_final_top_k
        )
        return _state_update(state=state,fused_rows=fusion_rows)

    def expand_parent_node(state:QueryState) -> QueryState:
        fused_rows = state.fused_rows
        parent_ids = [r["parent_id"] for r in fused_rows if r.get("parent_id") is not None]
        parent_map = parent_store.fetch_parent(parent_ids)
        blocks = []
        for row in fused_rows:
            parent = parent_map.get(row["parent_id"]) if row.get("parent_id") else None
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
        return _state_update(state=state,parent_rows=blocks)

    def generate_node(state:QueryState) -> QueryState:
        if state.skip_generate:
            return state
        answer = generate_answer(
            chat_model,
            question=state.query,
            context_blocks=state.parent_rows,
        )

        return _state_update(state=state,answer=answer)

    graph = StateGraph(QueryState)
    graph.add_node("vector", vector_node)
    graph.add_node("bm25", bm25_node)
    graph.add_node("fusion", fusion_node)
    graph.add_node("expand_parent", expand_parent_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "vector")
    graph.add_edge("vector", "bm25")
    graph.add_edge("bm25", "fusion")
    graph.add_edge("fusion", "expand_parent")
    graph.add_edge("expand_parent", "generate")
    graph.add_edge("generate", END)
    return graph.compile()







