"""
RAG Evaluation using RAGAS
Metrics: Faithfulness, Answer Relevancy, Context Recall
"""
from typing import List
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall

from app.core.config import get_settings
from app.retrieval.hybrid_retriever import hybrid_retrieve
from app.chains.rag_chain import query_rag

settings = get_settings()


def run_evaluation(test_cases: List[dict]) -> dict:
    """
    test_cases: list of {"question": str, "ground_truth": str}
    Returns RAGAS metric scores.
    """
    questions, answers, contexts, ground_truths = [], [], [], []

    for tc in test_cases:
        question = tc["question"]
        ground_truth = tc["ground_truth"]
        session_id = f"eval_{question[:20]}"

        # Get RAG answer
        result = query_rag(question, session_id)
        answer = result["answer"]

        # Get retrieved context texts
        retrieved = hybrid_retrieve(question)
        context_texts = [doc.page_content for doc in retrieved]

        questions.append(question)
        answers.append(answer)
        contexts.append(context_texts)
        ground_truths.append(ground_truth)

    # Build HuggingFace dataset for RAGAS
    eval_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    result = evaluate(
        eval_dataset,
        metrics=[faithfulness, answer_relevancy, context_recall],
    )

    return {
        "faithfulness": round(result["faithfulness"], 4),
        "answer_relevancy": round(result["answer_relevancy"], 4),
        "context_recall": round(result["context_recall"], 4),
        "num_samples": len(test_cases),
    }
