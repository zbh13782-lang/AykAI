from __future__ import annotations


class ElasticsearchBM25Retriever:
    def __init__(self,es_service,fallback = None):
        self.es_service = es_service
        self.fallback = fallback

    def retrieve(self,query:str,top_k:int = 20) -> list[dict]:
        if self.es_service.enabled:
            try:
                return self.es_service.bm25_search(query,top_k)
            except Exception as e:
                if self.fallback is None:
                    return []
                return self.fallback.retrieve(query,top_k)

        if self.fallback is None:
            return []
        return self.fallback.retrieve(query=query, top_k=top_k)