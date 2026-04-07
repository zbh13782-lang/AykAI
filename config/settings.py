from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="AykAI", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file_path: str = Field(default="logs/app.log", alias="LOG_FILE_PATH")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    openai_chat_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_CHAT_MODEL")

    milvus_uri: str = Field(default="http://localhost:19530", alias="MILVUS_URI")
    milvus_db_name: str = Field(default="default", alias="MILVUS_DB_NAME")
    milvus_child_collection: str = Field(default="rag_child_chunks", alias="MILVUS_CHILD_COLLECTION")
    milvus_vector_dim: int = Field(default=1536, alias="MILVUS_VECTOR_DIM")
    milvus_metric_type: str = Field(default="COSINE", alias="MILVUS_METRIC_TYPE")

    retrieval_vector_top_k: int = Field(default=20, alias="RETRIEVAL_VECTOR_TOP_K")
    retrieval_bm25_top_k: int = Field(default=20, alias="RETRIEVAL_BM25_TOP_K")
    retrieval_final_top_k: int = Field(default=8, alias="RETRIEVAL_FINAL_TOP_K")
    retrieval_fusion_strategy: str = Field(default="rrf", alias="RETRIEVAL_FUSION_STRATEGY")
    retrieval_rrf_k: int = Field(default=60, alias="RETRIEVAL_RRF_K")
    retrieval_vector_weight: float = Field(default=0.6, alias="RETRIEVAL_VECTOR_WEIGHT")
    retrieval_bm25_weight: float = Field(default=0.4, alias="RETRIEVAL_BM25_WEIGHT")
    retrieval_score_threshold: float = Field(default=0.0, alias="RETRIEVAL_SCORE_THRESHOLD")
    retrieval_dedup_by: str = Field(default="parent_id", alias="RETRIEVAL_DEDUP_BY")

    elasticsearch_url: str = Field(default="", alias="ELASTICSEARCH_URL")
    elasticsearch_index: str = Field(default="rag_child_chunks", alias="ELASTICSEARCH_INDEX")

    elasticsearch_vector_dim: int = Field(default=1536, alias="ELASTICSEARCH_VECTOR_DIM")

    elasticsearch_bulk_batch_size: int = Field(default=500, alias="ELASTICSEARCH_BULK_BATCH_SIZE")

    bm25_fallback_warmup_limit: int = Field(default=10000, alias="BM25_FALLBACK_WARMUP_LIMIT")
    bm25_fallback_warmup_batch_size: int = Field(default=500, alias="BM25_FALLBACK_WARMUP_BATCH_SIZE")
    ingest_write_retry_attempts: int = Field(default=2, alias="INGEST_WRITE_RETRY_ATTEMPTS")

    postgres_dsn: str = Field(default="postgresql://postgres:postgres@localhost:5432/ragent", alias="POSTGRES_DSN")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

