from config.settings import Settings
from typing import Any
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

'''后面考虑换pgvector了.....'''


class MilvusService:
    def __init__(self,settings:Settings):
        self.settings = settings
        self._connected = False

    def connect(self):
        if self._connected:
            return
        connections.connect(alias="default",url=self.settings.milvus_uri,db_name=self.settings.milvus_db_name)
        self._connected = True

    def init_collections(self) -> None:
        self.connect()
        if not utility.has_collection(self.settings.milvus_child_collection):
            child_fields = [
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256, is_primary=True),
                #注意要存parent_id！
                FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="chunk_order", dtype=DataType.INT64),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.settings.milvus_vector_dim),
            ]
            child_schema = CollectionSchema(fields=child_fields, description="Child chunks")
            child_collection = Collection(name=self.settings.milvus_child_collection, schema=child_schema)
            child_collection.create_index(
                field_name="embedding",
                index_params={
                    "index_type": "HNSW",
                    "metric_type": self.settings.milvus_metric_type,
                    "params": {"M": 16, "efConstruction": 200},
                },
            )

    def _child_collection(self) -> Collection:
        '''
        获取子块collection
        '''
        col = Collection(name=self.settings.milvus_child_collection)
        col.load()
        return col


    def upsert_children(self,rows:list[dict[str,Any]])->None:
        '''
        批量插入或更新子块
        '''
        if not rows:
            return
        col = self._child_collection()
        has_metadata = any(f.name == 'metadata' for f in col.schema.fields)
        if has_metadata:
            data = [
                [r["chunk_id"] for r in rows],
                [r["parent_id"] for r in rows],
                [r["doc_id"] for r in rows],
                [r["source"] for r in rows],
                [r["chunk_order"] for r in rows],
                [r["content"] for r in rows],
                [r.get("metadata", {}) for r in rows],
                [r["embedding"] for r in rows],
            ]
            col.upsert(data)
        else:
            data = [
                [r["chunk_id"] for r in rows],
                [r["parent_id"] for r in rows],
                [r["doc_id"] for r in rows],
                [r["source"] for r in rows],
                [r["chunk_order"] for r in rows],
                [r["content"] for r in rows],
                [r["embedding"] for r in rows],
            ]
            col.upsert(data)
        col.flush()

    def vector_search(self,query_vector:list[float],top_k:int)->list[dict[str,Any]]:
        col = self._child_collection()
        try:
            res = col.search(
                data=[query_vector],
                anns_field="embedding",
                params={"metric_type": self.settings.milvus_metric_type,"params":{"ef":64}},
                limit=top_k,
                output_fields=["chunk_id", "parent_id", "doc_id", "source", "chunk_order", "content"],
            )
        except Exception:
            # Backward compatibility for existing collections without metadata field.
            res = col.search(
                data=[query_vector],
                anns_field="embedding",
                param={"metric_type": self.settings.milvus_metric_type, "params": {"ef": 64}},
                limit=top_k,
                output_fields=["chunk_id", "parent_id", "doc_id", "source", "chunk_order", "content"],
            )
        out: list[dict[str, Any]] = []
        for hit in res[0]:
            out.append(
                {
                    "chunk_id": hit.entity.get("chunk_id"),
                    "parent_id": hit.entity.get("parent_id"),
                    "doc_id": hit.entity.get("doc_id"),
                    "source": hit.entity.get("source"),
                    "chunk_order": hit.entity.get("chunk_order"),
                    "content": hit.entity.get("content"),
                    "metadata": hit.entity.get("metadata") or {},
                    "score": float(hit.score),
                    "retrieval_source": "vector",
                }
            )
        return out


