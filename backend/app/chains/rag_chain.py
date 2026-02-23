"""
RAG Chain
- Conversational memory (per session)
- Hybrid retrieval
- Gemini chat model for answer generation
- Source citations
"""
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.core.config import get_settings
from app.retrieval.hybrid_retriever import hybrid_retrieve

settings = get_settings()

_session_memories: dict[str, ConversationBufferWindowMemory] = {}


def get_memory(session_id: str) -> ConversationBufferWindowMemory:
    if session_id not in _session_memories:
        _session_memories[session_id] = ConversationBufferWindowMemory(
            k=6,
            return_messages=True,
            memory_key="chat_history",
        )
    return _session_memories[session_id]


def clear_memory(session_id: str) -> None:
    _session_memories.pop(session_id, None)


@lru_cache()
def get_llm() -> ChatGoogleGenerativeAI:
    """
    Build chat model with compatibility fallback for free-tier API keys.
    """
    candidates = [
        settings.GEMINI_MODEL,
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-pro-latest",
    ]
    tried: list[str] = []

    for model_name in dict.fromkeys(candidates):
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,
        )
        try:
            llm.invoke("healthcheck")
            return llm
        except Exception as e:
            msg = str(e).lower()
            model_unavailable = (
                "not found" in msg
                or "not supported" in msg
                or "forbidden" in msg
                or "permission" in msg
                or "404" in msg
            )
            if not model_unavailable:
                raise
            tried.append(model_name)

    raise RuntimeError(
        "No supported Gemini chat model for this API key. Tried: " + ", ".join(tried)
    )


RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are EnterpriseRAG, an expert assistant for internal company documents.

Answer the user's question using ONLY the context provided below.
Rules:
1. Be concise and factual.
2. Always cite your source at the end in this format:
   Source: <filename> | Page <page> | Confidence: <High/Medium/Low>
3. If the answer is not in the context, say "I couldn't find this in the provided documents."
4. Never make up information.

CONTEXT:
{context}
""",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ]
)


def format_context(docs) -> str:
    parts = []
    for doc in docs:
        src = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        parts.append(f"[Source: {src} | Page: {page}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def query_rag(question: str, session_id: str) -> dict:
    memory = get_memory(session_id)
    llm = get_llm()

    retrieved_docs = hybrid_retrieve(question)
    context = format_context(retrieved_docs)

    chat_history = memory.chat_memory.messages
    prompt_value = RAG_PROMPT.format_messages(
        context=context,
        chat_history=chat_history,
        question=question,
    )

    response = llm.invoke(prompt_value)
    answer = response.content

    memory.chat_memory.add_user_message(question)
    memory.chat_memory.add_ai_message(answer)

    sources = []
    seen = set()
    for doc in retrieved_docs:
        src = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        key = f"{src}:{page}"
        if key not in seen:
            seen.add(key)
            sources.append({"filename": src, "page": page})

    return {
        "answer": answer,
        "sources": sources,
        "session_id": session_id,
    }