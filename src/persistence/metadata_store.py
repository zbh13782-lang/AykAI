from pathlib import Path
from typing import Any
import json
'''
后续优化点：换用es
'''
class JsonMetadataStore:
    def __init__(self, path:str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save_bm25_docs(self,docs : list[dict[str,Any]]) -> None:
        self.path.write_text(json.dumps(docs, ensure_ascii=True, indent=2), encoding="utf-8")

    def load_bm25_docs(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []