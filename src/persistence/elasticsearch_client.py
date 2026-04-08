from __future__ import annotations

import logging
from typing import Any
from elasticsearch import Elasticsearch

from config.settings import Settings

'''
靠ik分词实现分词，这样对中文关键词更友好

'''
logger = logging.getLogger(__name__)

class ElasticsearchService:
    def __init__(self,settings: Settings):
        self.settings = settings
        self._client:Elasticsearch | None = None
        self._ik_available: bool = False

    @property
    def enabled(self) -> bool:
        return bool(self.settings.elasticsearch_url.strip())

    def connect(self) -> Elasticsearch | None:
        if not self.enabled:
            return None
        if self._client is None:
            self._client = Elasticsearch(self.settings.elasticsearch_url)
        return self._client

    def _init_index(self) -> None:
        client = self.connect()
        if client is None:
            return

        index_name = self.settings.elasticsearch_index
        self._ik_available = self._detect_ik_available(client)
        if client.indices.exists(index=index_name):
            return

        mapping: dict[str, Any]
        if self._ik_available:
            mapping = {
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "ik_index_analyzer": {
                                "type": "custom",
                                "tokenizer": "ik_max_word",
                            },
                            "ik_search_analyzer": {
                                "type": "custom",
                                "tokenizer": "ik_smart",
                            },
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "parent_id": {"type": "keyword"},
                        "doc_id": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "chunk_order": {"type": "integer"},
                        "content": {
                            "type": "text",
                            "analyzer": "ik_index_analyzer",
                            "search_analyzer": "ik_search_analyzer",
                        },
                        "metadata": {"type": "object", "dynamic": True},
                    }
                },
            }
        else:
            mapping = {
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "parent_id": {"type": "keyword"},
                        "doc_id": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "chunk_order": {"type": "integer"},
                        "content": {"type": "text"},
                        "metadata": {"type": "object", "dynamic": True},
                    }
                },
            }
            logger.warning("ik_tokenizer_unavailable_use_standard_analyzer")

        try:
            client.indices.create(index=index_name, body=mapping, ignore=[400, 404])
        except Exception as exc:  # noqa: BLE001
            logger.exception("elasticsearch_create_index_failed error=%s", exc)
            raise RuntimeError(
                "Failed to create Elasticsearch index with IK analyzers. Ensure analysis-ik plugin is installed."
            ) from exc

    def init_index(self) -> None:
        self._init_index()

    @staticmethod
    def _detect_ik_available(client: Elasticsearch) -> bool:
        try:
            client.indices.analyze(body={"tokenizer": "ik_smart", "text": "test"})
            return True
        except Exception:  # noqa: BLE001
            return False

    def upsert_children(self,rows:list[dict[str, Any]]) -> None:
        client = self.connect()
        if client is None or not rows:
            return

        batch_size = max(1, self.settings.elasticsearch_bulk_batch_size)

        for i in range(0,len(rows),batch_size):
            batch = rows[i:i + batch_size]
            ops: list[dict[str, Any]] = []

            for row in batch:
                ops.append({"index": {"_index": self.settings.elasticsearch_index, "_id": row["chunk_id"]}})
                ops.append(
                    {
                        "chunk_id": row["chunk_id"],
                        "parent_id": row["parent_id"],
                        "doc_id": row["doc_id"],
                        "source": row["source"],
                        "chunk_order": row["chunk_order"],
                        "content": row["content"],
                        "metadata": row.get("metadata", {}),
                    }
                )

            result = client.bulk(operations=ops, refresh="wait_for")
            if not result.get("errors", False):
                continue

            failed_items: list[dict[str, Any]] = []
            for item in result.get("items", []):
                idx = item.get("index", {})
                status = int(idx.get("status", 0))
                if 200 <= status < 300:
                    continue
                failed_items.append(
                    {
                        "_id": idx.get("_id"),
                        "status": status,
                        "error": idx.get("error"),
                    }
                )

            if failed_items:
                logger.error(
                    "elasticsearch_bulk_partial_failure index=%s batch_start=%s failed=%s",
                    self.settings.elasticsearch_index,
                    i,
                    failed_items[:5],
                )
                raise RuntimeError(f"Elasticsearch bulk upsert failed for {len(failed_items)} items")

    def bm25_search(self,query:str,top_k:int = 8) -> list[dict[str, Any]]:
        client = self.connect()
        if client is None:
            return []

        try :
            result = client.search(
                index = self.settings.elasticsearch_index,
                query={"match": {"content": {"query": query}}},
                size=top_k,
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning("elasticsearch_bm25_search_failed error=%s", exc)
            raise
        return self._hits_to_rows(result.get("hits", {}).get("hits", []), retrieval_source="bm25")

    def scan_bm25_docs(self, limit: int = 10000, batch_size: int = 500) -> list[dict[str, Any]]:
        client = self.connect()
        if client is None or limit <= 0:
            return []

        size = max(1, min(batch_size, limit))
        collected: list[dict[str, Any]] = []
        search_after = None

        while len(collected) < limit:
            body: dict[str, Any] = {
                "query": {"match_all": {}},
                "size": min(size, limit - len(collected)),
                "sort": [{"chunk_id": "asc"}],
                "_source": ["chunk_id", "parent_id", "doc_id", "source", "chunk_order", "content", "metadata"],
            }
            if search_after is not None:
                body["search_after"] = search_after

            result = client.search(index=self.settings.elasticsearch_index, **body)
            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                src = hit.get("_source", {})
                collected.append(
                    {
                        "chunk_id": src.get("chunk_id"),
                        "parent_id": src.get("parent_id"),
                        "doc_id": src.get("doc_id"),
                        "source": src.get("source"),
                        "chunk_order": src.get("chunk_order"),
                        "content": src.get("content", ""),
                        "metadata": src.get("metadata") or {},
                    }
                )
                if len(collected) >= limit:
                    break

            search_after = hits[-1].get("sort")
            if search_after is None:
                break

        return collected

    @staticmethod
    def _hits_to_rows(hits: list[dict[str, Any]], retrieval_source: str) -> list[dict[str, Any]]:
        """
           将ES返回的原始hits转换为标准化的文档行格式
           输入：ES原始结果 + 检索来源标识
           输出：标准化的文档列表
           作用：统一不同检索来源的结果格式
        """
        rows: list[dict[str, Any]] = []
        for hit in hits:
            src = hit.get("_source", {})
            rows.append(
                {
                    "chunk_id": src.get("chunk_id"),
                    "parent_id": src.get("parent_id"),
                    "doc_id": src.get("doc_id"),
                    "source": src.get("source"),
                    "chunk_order": src.get("chunk_order"),
                    "content": src.get("content", ""),
                    "metadata": src.get("metadata") or {},
                    "score": float(hit.get("_score", 0.0)),
                    "retrieval_source": retrieval_source,
                }
            )
        return rows










