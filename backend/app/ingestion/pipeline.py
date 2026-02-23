"""
Ingestion Pipeline
- Loads PDF / DOCX / TXT files
- Splits into semantic chunks with overlap
- Embeds with Google Generative AI embeddings
- Stores in ChromaDB
"""
import uuid
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai._common import GoogleGenerativeAIError
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

settings = get_settings()


@lru_cache()
def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    Build embeddings with a compatibility fallback for free-tier Gemini keys.
    Some keys do not support text-embedding-004 on the v1beta embed endpoint.
    """
    candidates = [
        settings.EMBEDDING_MODEL,
        "models/gemini-embedding-001",
        "models/text-embedding-004",
        "models/embedding-001",
    ]
    tried: list[str] = []

    for model_name in dict.fromkeys(candidates):
        emb = GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        try:
            emb.embed_query("healthcheck")
            return emb
        except GoogleGenerativeAIError as e:
            msg = str(e).lower()
            model_unavailable = (
                "not found" in msg
                or "not supported" in msg
                or "forbidden" in msg
                or "permission" in msg
            )
            if not model_unavailable:
                raise
            tried.append(model_name)

    raise RuntimeError(
        "No supported Gemini embedding model for this API key. Tried: "
        + ", ".join(tried)
    )


@lru_cache()
def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=settings.CHROMA_PERSIST_DIR,
        client_settings=ChromaSettings(anonymized_telemetry=False),
    )


def load_document(file_path: str) -> List[Document]:
    ext = Path(file_path).suffix.lower()
    loaders = {
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".txt": TextLoader,
    }
    loader_cls = loaders.get(ext)
    if not loader_cls:
        raise ValueError(f"Unsupported file type: {ext}")
    return loader_cls(file_path).load()


def chunk_documents(docs: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = str(uuid.uuid4())
        chunk.metadata["chunk_index"] = i

    return chunks


def ingest_file(file_path: str, filename: str) -> dict:
    """
    Full pipeline: load -> chunk -> embed -> store.
    Returns summary stats.
    """
    docs = load_document(file_path)

    for doc in docs:
        doc.metadata["source"] = filename
        doc.metadata.setdefault("page", doc.metadata.get("page", 0))

    chunks = chunk_documents(docs)

    vector_store = get_vector_store()
    vector_store.add_documents(chunks)

    return {
        "filename": filename,
        "total_pages": len(docs),
        "total_chunks": len(chunks),
        "status": "success",
    }


def list_ingested_sources() -> List[str]:
    """Return distinct source filenames in the vector store."""
    store = get_vector_store()
    results = store.get(include=["metadatas"])
    sources = {m.get("source", "unknown") for m in results["metadatas"]}
    return sorted(sources)
