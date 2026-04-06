from functools import lru_cache

from config.settings import get_settings
from indexing.ingest_graph import build_ingest_graph
from llm.llm_wrapper import build_embeddings, build_chat_model
from persistence.metadata_store import JsonMetadataStore
from persistence.milvus_client import MilvusService
from persistence.parent_store import PostgresParentStore
from retrieval.bm25_retriever import BM25Retriever
from retrieval.query_graph import build_query_graph
from retrieval.vector_retriever import VectorRetriever


@lru_cache(maxsize=1)
def get_services():
    settings = get_settings()
    milvus_service = MilvusService(settings)
    milvus_service.init_collections()
    parent_store = PostgresParentStore(settings.postgres_dsn)
    parent_store.init_schema()

    metadata_store = JsonMetadataStore(settings.bm25_snapshot_path)
    embeddings = build_embeddings(settings)
    chat_model = build_chat_model(settings)

    vector_retriever = VectorRetriever(embeddings=embeddings,milvus_service=milvus_service,settings=settings)
    bm25_retriever = BM25Retriever(metadata_store=metadata_store)
    bm25_retriever.refresh()

    ingest_graph = build_ingest_graph(
        embeddings=embeddings,
        milvus_service=milvus_service,
        metadata_store=metadata_store,
        parent_store=parent_store,
    )

    query_graph = build_query_graph(
        settings=settings,
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever,
        parent_store=parent_store,
        chat_model=chat_model,
    )

    return {
        "settings": settings,
        "milvus_service": milvus_service,
        "parent_store": parent_store,
        "metadata_store": metadata_store,
        "bm25_retriever": bm25_retriever,
        "chat_model": chat_model,
        "ingest_graph": ingest_graph,
        "query_graph": query_graph,
    }