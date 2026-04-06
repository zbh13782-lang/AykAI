import os

from pymilvus import utility

from config.settings import get_settings
from src.persistence.milvus_client import MilvusService

LEGACY_PARENT_COLLECTION = "rag_parent_chunks"


def main() -> None:
    settings = get_settings()
    service = MilvusService(settings)
    service.init_collections()
    if os.getenv("CLEANUP_LEGACY_PARENT", "0") == "1" and utility.has_collection(LEGACY_PARENT_COLLECTION):
        utility.drop_collection(LEGACY_PARENT_COLLECTION)
        print(f"dropped legacy collection: {LEGACY_PARENT_COLLECTION}")
    print("milvus collections initialized")


if __name__ == "__main__":
    main()