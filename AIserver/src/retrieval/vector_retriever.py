from config.settings import Settings
'''
向量检索器封装
第二种检索方式，主要是封装一下
'''

class VectorRetriever:
    def __init__(self,embeddings,milvus_service,settings:Settings):
        self.embeddings = embeddings
        self.milvus_service = milvus_service
        self.settings = settings

    def retrieve(self, query: str, top_k: int | None = None, owner_id: str | None = None) -> list[dict]:
        query_vector = self.embeddings.embed_query(query)
        limit = top_k or self.settings.retrieval_vector_top_k
        search_limit = max(limit, limit * 8) if owner_id else limit
        return self.milvus_service.vector_search(
            query_vector=query_vector,
            top_k=search_limit,
            owner_id=owner_id,
            final_top_k=limit,
        )
