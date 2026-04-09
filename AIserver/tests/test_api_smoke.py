from types import SimpleNamespace

from fastapi.testclient import TestClient

import api.main as main_module
import api.routes.health as health_route
import api.routes.ingest as ingest_route
import api.routes.query as query_route


class _FakeBM25Retriever:
    def __init__(self) -> None:
        self.refreshed = False

    def refresh(self) -> None:
        self.refreshed = True


class _FakeIngestGraph:
    def invoke(self, _input: dict) -> dict:
        return {"inserted_parents": 1, "inserted_children": 2}


class _FakeQueryGraph:
    def invoke(self, payload: dict) -> dict:
        if payload.get("skip_generate"):
            return {
                "parent_rows": [
                    {
                        "source": "smoke",
                        "doc_id": "doc-1",
                        "content": "hello",
                        "metadata": {},
                    }
                ]
            }
        return {
            "answer": "ok",
            "parent_rows": [
                {
                    "source": "smoke",
                    "doc_id": "doc-1",
                    "content": "hello",
                    "metadata": {},
                }
            ],
        }


def _fake_stream_answer(_chat_model, _query: str, _refs: list[dict]):
    yield "he"
    yield "llo"


def _install_fake_services(monkeypatch):
    fake_services = {
        "settings": SimpleNamespace(app_name="AykAI"),
        "bm25_retriever": _FakeBM25Retriever(),
        "ingest_graph": _FakeIngestGraph(),
        "query_graph": _FakeQueryGraph(),
        "chat_model": object(),
    }

    monkeypatch.setattr(
        health_route,
        "get_settings",
        lambda: SimpleNamespace(app_name="AykAI"),
    )
    monkeypatch.setattr(ingest_route, "get_services", lambda: fake_services)
    monkeypatch.setattr(query_route, "get_services", lambda: fake_services)
    monkeypatch.setattr(query_route, "stream_answer", _fake_stream_answer)
    return fake_services


def test_health(monkeypatch):
    _install_fake_services(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "app": "AykAI"}


def test_ingest(monkeypatch):
    _install_fake_services(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.post(
        "/api/ingest",
        json={
            "doc_id": "doc-1",
            "source": "manual",
            "content": "hello world",
            "metadata": {"k": "v"},
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "inserted_parents": 1, "inserted_children": 2}


def test_query(monkeypatch):
    _install_fake_services(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.post("/api/query", json={"query": "what?", "stream": False})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["answer"] == "ok"
    assert len(body["references"]) == 1


def test_query_stream(monkeypatch):
    _install_fake_services(monkeypatch)
    client = TestClient(main_module.app)

    resp = client.post("/api/query/stream", json={"query": "what?", "stream": True})

    assert resp.status_code == 200
    assert '"event": "references"' in resp.text
    assert '"event": "token"' in resp.text