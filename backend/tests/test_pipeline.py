"""
Unit tests for the RAG pipeline
Run with: pytest tests/ -v
"""
import pytest
from unittest.mock import patch, MagicMock
from app.ingestion.pipeline import chunk_documents
from langchain.schema import Document


# ── Chunking tests ────────────────────────────────────────────────────────────
def test_chunk_documents_basic():
    docs = [Document(page_content="Hello world. " * 200, metadata={"source": "test.pdf", "page": 1})]
    chunks = chunk_documents(docs)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.page_content) <= 1200  # chunk_size + some buffer
        assert "chunk_id" in chunk.metadata


def test_chunk_preserves_metadata():
    docs = [Document(page_content="Some content " * 100, metadata={"source": "policy.pdf", "page": 5})]
    chunks = chunk_documents(docs)
    for chunk in chunks:
        assert chunk.metadata["source"] == "policy.pdf"
        assert chunk.metadata["page"] == 5


def test_chunk_assigns_unique_ids():
    docs = [Document(page_content="Content " * 300, metadata={"source": "a.pdf"})]
    chunks = chunk_documents(docs)
    ids = [c.metadata["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_ids must be unique"


# ── RAG chain tests ───────────────────────────────────────────────────────────
def test_memory_is_per_session():
    from app.chains.rag_chain import get_memory, clear_memory
    mem1 = get_memory("session_a")
    mem2 = get_memory("session_b")
    assert mem1 is not mem2


def test_clear_memory():
    from app.chains.rag_chain import get_memory, clear_memory, _session_memories
    get_memory("to_clear")
    assert "to_clear" in _session_memories
    clear_memory("to_clear")
    assert "to_clear" not in _session_memories


# ── API tests ─────────────────────────────────────────────────────────────────
def test_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_empty_question():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.post("/chat", json={"question": "  ", "session_id": "test"})
    assert resp.status_code == 400


def test_upload_invalid_extension():
    from fastapi.testclient import TestClient
    from app.main import app
    import io
    client = TestClient(app)
    resp = client.post(
        "/upload",
        files={"file": ("test.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert resp.status_code == 400
