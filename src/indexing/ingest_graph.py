from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import START, END, StateGraph

from src.indexing.parent_child_builder import build_index_records

#数据处理管道
#chunk->embed->upsert


class IngestState(TypedDict,total=False):
    '''文档处理状态,字段可选'''
    doc_id: str
    source: str
    content: str
    metadata: dict[str, Any]
    parents: list[dict[str, Any]]
    children: list[dict[str, Any]]
    child_embeddings: list[list[float]]
    inserted_children: int          #已插入的子块数量
    inserted_parents: int           #已插入父块数量

def build_ingest_graph(embeddings,milvus_service,metadata,parent_store):

    #节点1：chunk_node  文档分块
    def chunk_node(state:IngestState) -> IngestState:
        parents,children = build_index_records(
            doc_id=state['doc_id'],
            source=state['source'],
            content=state['content'],
            metadata=state['metadata'],
        )

        return {
            **state,
            "parents": [p.__dict__ for p in parents],
            "children": [c.__dict__ for c in children],
        }

    #节点2：embed_node 向量化
    def embed_node(state:IngestState) -> IngestState:
        texts = [c["content"] for c in state["children"]]
        vectors = embeddings.enbed_documents(texts)
        return {
            **state,
            "child_embeddings": vectors,
        }

    #节点3:upsert_node 入库 todo

