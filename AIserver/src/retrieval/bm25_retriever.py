from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from threading import RLock
from typing import Any
import jieba

'''
这里是一个可以优化点，目前已变为降级方案，当es崩了用这个

～～ bm25检索器实现，关键词匹配(第二种检索方式)～～
～～这里直接用内存索引，目前主要支持英文（按空格划分），中文我直接一个字当关键词了，但这样不太对( 好像非常不合理？？)，后面再改吧～～
～～后面改es更好 或者（备选）： milvus直接指定一个varchar字段去存储～～
～～区别主要在中文分词方面：es对中文分词更友好，milvus对中文不太好，后面我就准备换es了～～
'''


class BM25InvertedIndexRetriever:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._lock = RLock()
        self._docs: dict[str, dict[str, Any]] = {}
        self._doc_tokens: dict[str, Counter[str]] = {}
        self._doc_len: dict[str, int] = {}
        self._inverted_index: dict[str, dict[str, int]] = defaultdict(dict)
        self._avgdl: float = 0.0

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = (text or "").lower().strip()
        if not normalized:
            return []

        tokens: list[str] = []
        for token in jieba.lcut(normalized, cut_all=False):
            cleaned = token.strip()
            if not cleaned:
                continue
            if re.fullmatch(r"[\u4e00-\u9fff]+|[a-z0-9]+(?:['_-][a-z0-9]+)*", cleaned):
                tokens.append(cleaned)
                continue
            parts = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+(?:['_-][a-z0-9]+)*", cleaned)
            tokens.extend(parts)
        return tokens

    def _recompute_avgdl(self) -> None:
        if not self._doc_len:
            self._avgdl = 0.0
            return
        self._avgdl = float(sum(self._doc_len.values())) / float(len(self._doc_len))

    def _remove_doc(self, chunk_id: str) -> None:
        if chunk_id not in self._doc_tokens:
            return
        for token in self._doc_tokens[chunk_id].keys():
            posting = self._inverted_index.get(token)
            if posting is None:
                continue
            posting.pop(chunk_id, None)
            if not posting:
                self._inverted_index.pop(token, None)
        self._doc_tokens.pop(chunk_id, None)
        self._doc_len.pop(chunk_id, None)
        self._docs.pop(chunk_id, None)

    def upsert_children(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with self._lock:
            for row in rows:
                chunk_id = str(row["chunk_id"])
                self._remove_doc(chunk_id)

                tokens = self._tokenize(str(row.get("content", "")))
                if not tokens:
                    continue
                token_counts = Counter(tokens)

                doc_row = {
                    "chunk_id": row.get("chunk_id"),
                    "parent_id": row.get("parent_id"),
                    "doc_id": row.get("doc_id"),
                    "source": row.get("source"),
                    "chunk_order": row.get("chunk_order"),
                    "content": row.get("content", ""),
                    "metadata": row.get("metadata") or {},
                }
                self._docs[chunk_id] = doc_row
                self._doc_tokens[chunk_id] = token_counts
                self._doc_len[chunk_id] = len(tokens)

                for token, tf in token_counts.items():
                    self._inverted_index[token][chunk_id] = int(tf)

            self._recompute_avgdl()

    def retrieve(self, query: str, top_k: int = 20, owner_id: str | None = None) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        with self._lock:
            total_docs = len(self._docs)
            if total_docs == 0:
                return []

            candidate_chunk_ids: set[str] = set()
            for token in query_tokens:
                candidate_chunk_ids.update(self._inverted_index.get(token, {}).keys())
            if not candidate_chunk_ids:
                return []

            scores: dict[str, float] = defaultdict(float)
            unique_query_tokens = set(query_tokens)

            for token in unique_query_tokens:
                posting = self._inverted_index.get(token)
                if not posting:
                    continue
                df = len(posting)
                idf = math.log(1.0 + (total_docs - df + 0.5) / (df + 0.5))

                for chunk_id, tf in posting.items():
                    if chunk_id not in candidate_chunk_ids:
                        continue
                    dl = self._doc_len.get(chunk_id, 0)
                    avgdl = self._avgdl if self._avgdl > 0 else 1.0
                    denom = float(tf) + self.k1 * (1.0 - self.b + self.b * float(dl) / avgdl)
                    if denom <= 0:
                        continue
                    term_score = idf * (float(tf) * (self.k1 + 1.0) / denom)
                    scores[chunk_id] += term_score

            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            results: list[dict[str, Any]] = []
            for chunk_id, score in ranked:
                doc = self._docs[chunk_id]
                if owner_id and str((doc.get("metadata") or {}).get("owner_id", "")) != owner_id:
                    continue
                results.append({**doc, "score": float(score), "retrieval_source": "bm25"})
                if len(results) >= top_k:
                    break
            return results
