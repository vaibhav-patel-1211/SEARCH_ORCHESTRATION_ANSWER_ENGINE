from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

from config import model
from prompts.prompts import document_router_system_prompt
from schemas.document_schema import DocumentRouteDecision

DOCUMENT_HINTS = (
    "uploaded",
    "document",
    "pdf",
    "file",
    "paper",
    "resume",
    "résumé",
    "cv",
    "according to",
    "in the document",
    "this document",
    "this file",
    "this resume",
    "from the file",
    "summarize the pdf",
)

WEB_HINTS = (
    "latest",
    "current",
    "recent",
    "today",
    "news",
    "web",
    "internet",
    "online",
)


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in hints)


async def document_intent_node(state):
    uploaded_files = state.get("uploaded_files", [])
    query = state.get("prompt", "")
    previous_route = state.get("route_source", "")

    if not uploaded_files:
        return {
            "route_source": "web",
            "document_query_reason": "No uploaded files are associated with this session.",
            "document_query_confidence": 1.0,
        }

    has_document_hint = _contains_any(query, DOCUMENT_HINTS)
    has_web_hint = _contains_any(query, WEB_HINTS)

    # If user explicitly asks for document content
    if has_document_hint and not has_web_hint:
        return {
            "route_source": "document",
            "document_query_reason": "Query explicitly references uploaded document(s).",
            "document_query_confidence": 0.95,
        }

    # If user asks for both
    if has_document_hint and has_web_hint:
        return {
            "route_source": "hybrid",
            "document_query_reason": "Query references both uploaded content and external context.",
            "document_query_confidence": 0.9,
        }

    # Strong web signal override
    if has_web_hint and not has_document_hint:
        # Check if the query could still be about the document (e.g. "latest version of the architecture in this pdf")
        # But usually "latest" implies web.
        return {
            "route_source": "web",
            "document_query_reason": "Query requests current or external web information.",
            "document_query_confidence": 0.9,
        }

    # DEFAULT for when files are uploaded: 
    # If no explicit web hint, and files are available, ALWAYS try document first.
    # This covers "What is machine learning?" when a ML paper is uploaded.
    if not has_web_hint:
        return {
            "route_source": "document",
            "document_query_reason": "Uploaded files are available and no explicit web signal detected. Prioritizing documents.",
            "document_query_confidence": 0.85,
        }

    # Fallback to LLM if ambiguous
    file_names = ", ".join(file.get("filename", "") for file in uploaded_files if isinstance(file, dict))
    structured_llm = model.with_structured_output(DocumentRouteDecision)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", document_router_system_prompt),
            (
                "human",
                "query: {query}\nprevious_route: {previous_route}\nuploaded_files: {file_names}",
            ),
        ]
    )
    chain = prompt | structured_llm
    try:
        decision = await chain.ainvoke(
            {
                "query": query,
                "previous_route": previous_route or "none",
                "file_names": file_names or "none",
            }
        )
        return {
            "route_source": decision.route_source,
            "document_query_reason": decision.reason,
            "document_query_confidence": decision.confidence,
        }
    except Exception as e:
        print(f"⚠️ Document routing LLM failed: {e}. Defaulting to hybrid.")
        return {
            "route_source": "hybrid",
            "document_query_reason": "LLM routing failed, defaulting to hybrid for safety.",
            "document_query_confidence": 0.5,
        }

