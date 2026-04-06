from __future__ import annotations

import re
from pathlib import Path

from rank_bm25 import BM25Okapi
'''

这里是一个可以优化点，todo
bm25检索器实现，关键词匹配(第二种检索方式)
这里直接用内存索引，目前主要支持英文（按空格划分），中文我直接一个字当关键词了，但这样不太对( 好像非常不合理？？)，后面再改吧
后面改es更好 或者（备选）： milvus直接指定一个varchar字段去存储
区别主要在中文分词方面：es对中文分词更友好，milvus对中文不太好，后面我就准备换es了
'''
class BM25Retriever:
    def __init__(self,metadata_store):
        self.metadata_store = metadata_store
        self._docs : list[dict] = []
        self._bm25 : BM25Okapi | None = None
        self._snapshot_signature: tuple[int, int] | None = None         #存修改时间戳和文件大小

    @staticmethod
    def _tokenize(text : str) -> list[str]:
        '''
        文本转换为小写并按空格分词，但对中文不太友好
        '''
        normalized = text.lower().strip()
        if not normalized:
            return []

        tokens = re.findall(r"[a-z0-9]+(?:['_-][a-z0-9]+)*|[\u4e00-\u9fff]", normalized)
        return tokens or [normalized]

    def refresh(self) -> None:
        self._docs = self.metadata_store.load_bm25_docs()
        corpus = [self._tokenize(d["content"]) for d in self._docs]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        self._snapshot_signature = self._read_snapshot_signature()

    def _read_snapshot_signature(self) -> tuple[int, int] | None:
        '''读取快照签名'''
        path = getattr(self.metadata_store, "path", None)
        if path is None:
            return None

        snapshot_path = Path(path)
        try:
            stat = snapshot_path.stat()
            return (int(stat.st_mtime_ns), int(stat.st_size))
        except FileNotFoundError:
            return (-1, 0)

    def _refresh_if_needed(self) -> None:
        '''
        智能刷新机制，先拿到文件签名，拿不到就简单刷新逻辑，文件更改了也刷新
        '''
        current_signature = self._read_snapshot_signature()
        if current_signature is None:
            if self._bm25 is None:
                self.refresh()
            return

        if self._bm25 is None or current_signature != self._snapshot_signature:
            self.refresh()

    def retrieve(self,query,top_k:int = 20) -> list[dict]:
        self._refresh_if_needed()
        if self._bm25 is None:
            return []
        tokens = self._tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked_idx = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)[:top_k]

        results = []
        for idx in ranked_idx:
            doc = self._docs[idx]
            results.append(
                {
                    **doc,
                    "score" : float(scores[idx]),
                    "retrieval_source" : "bm25",
                }
            )
        return results
