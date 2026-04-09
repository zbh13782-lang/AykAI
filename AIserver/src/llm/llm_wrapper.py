from config.settings import Settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def _normalize_base_url(base_url: str) -> str:
    # 兼容 /chat/completions 的情况，自动回退到 API 根路径。
    url = (base_url or "").strip()
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url[: -len("/chat/completions")]
    return url.rstrip("/")

def build_embeddings(settings:Settings) -> OpenAIEmbeddings:
    base_url = _normalize_base_url(settings.openai_base_url)
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
        base_url=base_url or None,
    )

def build_chat_model(settings:Settings) -> ChatOpenAI:
    base_url = _normalize_base_url(settings.openai_base_url)
    return ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key,
        base_url=base_url or None,
        temperature=0.1
    )