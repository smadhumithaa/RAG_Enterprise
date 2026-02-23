"""
FastAPI Application
Routes:
  POST /upload          — ingest a document
  POST /chat            — ask a question
  DELETE /chat/session  — clear session memory
  GET  /sources         — list ingested documents
  POST /evaluate        — run RAGAS evaluation
"""
import os
import uuid
import shutil
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import get_settings
from app.ingestion.pipeline import ingest_file, list_ingested_sources
from app.chains.rag_chain import query_rag, clear_memory

settings = get_settings()

app = FastAPI(
    title="EnterpriseRAG API",
    description="Production RAG system for enterprise knowledge bases",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",


    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/tmp/rag_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    session_id: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str


class EvalRequest(BaseModel):
    test_cases: List[dict]   # [{"question": ..., "ground_truth": ...}]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Ingest a PDF, DOCX, or TXT file into the vector store."""
    allowed = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")

    # Save temporarily
    tmp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = ingest_file(tmp_path, file.filename)
    finally:
        os.remove(tmp_path)

    return result


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Ask a question. Maintains per-session conversation memory."""
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty.")

    session_id = req.session_id or str(uuid.uuid4())

    try:
        result = query_rag(req.question, session_id)
    except Exception as e:
        raise HTTPException(500, f"RAG chain error: {str(e)}")

    return ChatResponse(**result)


@app.delete("/chat/session/{session_id}")
def clear_session(session_id: str):
    """Clear conversation memory for a session."""
    clear_memory(session_id)
    return {"message": f"Session {session_id} cleared."}


@app.get("/sources")
def get_sources():
    """List all documents that have been ingested."""
    sources = list_ingested_sources()
    return {"sources": sources, "count": len(sources)}


@app.post("/evaluate")
def evaluate(req: EvalRequest):
    """Run RAGAS evaluation on a set of test Q&A pairs."""
    if not req.test_cases:
        raise HTTPException(400, "Provide at least one test case.")

    # Import here to avoid slow startup
    from app.evaluation.ragas_eval import run_evaluation
    results = run_evaluation(req.test_cases)
    return results
