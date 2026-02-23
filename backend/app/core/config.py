from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # Google / Gemini
    GOOGLE_API_KEY: str

    # LLM config
    GEMINI_MODEL: str = "models/gemini-2.5-flash"
    # Free-tier keys commonly support gemini-embedding-001.
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # Chunking
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Retrieval
    TOP_K_DENSE: int = 5
    TOP_K_SPARSE: int = 5
    TOP_K_FINAL: int = 4          # after re-ranking

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "enterprise_docs"

    # App
    APP_NAME: str = "EnterpriseRAG"
    DEBUG: bool = False

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
