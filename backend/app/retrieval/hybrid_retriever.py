"""
Hybrid Retriever
- Dense retrieval: ChromaDB cosine similarity (Google embeddings)
- Sparse retrieval: BM25 keyword search
- Reciprocal Rank Fusion to merge results
- Cross-encoder re-ranking for final top-K
"""
from typing import List, Tuple
from langchain.schema import Document
from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.ingestion.pipeline import get_vector_store

settings = get_settings()


def _reciprocal_rank_fusion(
    ranked_lists: List[List[Document]], k: int = 60
) -> List[Tuple[Document, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.
    Higher score = better. k=60 is the standard constant.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            doc_id = doc.metadata.get("chunk_id", doc.page_content[:80])
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            doc_map[doc_id] = doc

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [(doc_map[doc_id], scores[doc_id]) for doc_id in sorted_ids]


def hybrid_retrieve(query: str, all_docs: List[Document] | None = None) -> List[Document]:
    """
    1. Dense retrieval from ChromaDB
    2. BM25 sparse retrieval over stored chunks
    3. RRF merge
    4. Return top-K
    """
    vector_store = get_vector_store()

    # ── Dense retrieval ───────────────────────────────────────────────────────
    dense_results = vector_store.similarity_search(
        query, k=settings.TOP_K_DENSE
    )

    # ── Sparse retrieval (BM25) ───────────────────────────────────────────────
    # Fetch all stored chunks for BM25 indexing
    raw = vector_store.get(include=["documents", "metadatas"])
    corpus_texts = raw["documents"]
    corpus_metas = raw["metadatas"]

    if corpus_texts:
        tokenized_corpus = [doc.lower().split() for doc in corpus_texts]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(query.lower().split())

        # Get top-K sparse indices
        top_sparse_idx = sorted(
            range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
        )[: settings.TOP_K_SPARSE]

        sparse_results = [
            Document(
                page_content=corpus_texts[i],
                metadata=corpus_metas[i],
            )
            for i in top_sparse_idx
        ]
    else:
        sparse_results = []

    # ── Fuse + deduplicate ────────────────────────────────────────────────────
    fused = _reciprocal_rank_fusion([dense_results, sparse_results])
    top_docs = [doc for doc, _ in fused[: settings.TOP_K_FINAL]]

    return top_docs
