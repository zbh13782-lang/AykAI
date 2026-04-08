from functools import lru_cache
import logging

from config.settings import get_settings
from src.indexing.ingest_graph import build_ingest_graph
from src.llm.llm_wrapper import build_chat_model, build_embeddings
from src.persistence.elasticsearch_client import ElasticsearchService
from src.persistence.milvus_client import MilvusService
from src.persistence.parent_store import PostgresParentStore
from src.retrieval.bm25_retriever import BM25InvertedIndexRetriever
from src.retrieval.elasticsearch_retriever import ElasticsearchBM25Retriever
from src.retrieval.query_graph import build_query_graph
from src.retrieval.vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_services():
    settings = get_settings()
    milvus_service = MilvusService(settings)
    milvus_service.init_collections()
    parent_store = PostgresParentStore(settings.postgres_dsn)
    parent_store.init_schema()

    embeddings = build_embeddings(settings)
    chat_model = build_chat_model(settings)
    elasticsearch_service = ElasticsearchService(settings)
    try:
        elasticsearch_service.init_index()
    except Exception as exc:  # noqa: BLE001
        logger.warning("elasticsearch_unavailable_fallback_to_local_bm25 error=%s", exc)
        # Degrade gracefully when Elasticsearch is unavailable.
        elasticsearch_service.settings.elasticsearch_url = ""

    vector_retriever = VectorRetriever(embeddings=embeddings, milvus_service=milvus_service, settings=settings)
    local_bm25_retriever = BM25InvertedIndexRetriever()
    bm25_retriever = ElasticsearchBM25Retriever(es_service=elasticsearch_service, fallback=local_bm25_retriever)

    if elasticsearch_service.enabled:
        try:
            fallback_docs = elasticsearch_service.scan_bm25_docs(
                limit=settings.bm25_fallback_warmup_limit,
                batch_size=settings.bm25_fallback_warmup_batch_size,
            )
            local_bm25_retriever.upsert_children(fallback_docs)
        except Exception:  # noqa: BLE001
            # Startup should not fail solely because fallback warmup failed.
            pass

    ingest_graph = build_ingest_graph(
        embeddings=embeddings,
        milvus_service=milvus_service,
        parent_store=parent_store,
        semantic_indexer=elasticsearch_service,
        bm25_indexer=local_bm25_retriever,
        write_retry_attempts=settings.ingest_write_retry_attempts,
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
        "elasticsearch_service": elasticsearch_service,
        "bm25_retriever": bm25_retriever,
        "chat_model": chat_model,
        "ingest_graph": ingest_graph,
        "query_graph": query_graph,
    }
