from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from schemas.ws_schema import RetrievedDocument, RetrievalEvent, TokenEvent, ToolCallEvent

FINAL_ANSWER_NODES = {"answer_node", "general_answer_node", "coding_node"}
TOKEN_EVENT_NAMES = {"on_chat_model_stream", "on_llm_stream"}
FINAL_STATE_KEYS = {"final_answer", "intent", "diagram_svg", "pdf_filename", "cache_hit"}


def _extract_node_name(event: dict[str, Any]) -> str | None:
    metadata = event.get("metadata")
    if isinstance(metadata, dict):
        node = metadata.get("langgraph_node")
        if isinstance(node, str):
            return node

        path = metadata.get("langgraph_path")
        if isinstance(path, (list, tuple)) and path:
            last_segment = path[-1]
            if isinstance(last_segment, str):
                return last_segment

    name = event.get("name")
    return name if isinstance(name, str) else None


def _extract_output(event: dict[str, Any], node_name: str | None) -> dict[str, Any]:
    data = event.get("data")
    if not isinstance(data, dict):
        return {}

    output = data.get("output")
    if not isinstance(output, dict):
        return {}

    if node_name and node_name in output and isinstance(output[node_name], dict):
        return output[node_name]

    return output


def _extract_text(chunk: Any) -> str:
    if isinstance(chunk, str):
        return chunk

    if hasattr(chunk, "text") and isinstance(chunk.text, str):
        return chunk.text

    if hasattr(chunk, "content"):
        content = chunk.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        text_parts.append(text)
            return "".join(text_parts)

    if isinstance(chunk, dict):
        text = chunk.get("text") or chunk.get("content")
        return text if isinstance(text, str) else ""

    return ""


def _extract_stream_token(event: dict[str, Any]) -> str:
    data = event.get("data")
    if not isinstance(data, dict):
        return ""
    return _extract_text(data.get("chunk"))


def _normalize_documents(raw_documents: Any) -> list[RetrievedDocument]:
    if not isinstance(raw_documents, list):
        return []

    normalized: list[RetrievedDocument] = []
    for item in raw_documents:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not title and url:
            title = urlparse(url).netloc or "Source"
        snippet = item.get("snippet")
        snippet_text = str(snippet).strip() if isinstance(snippet, str) else None
        normalized.append(
            RetrievedDocument(
                title=title or "Source",
                url=url,
                snippet=snippet_text or None,
            )
        )
    return normalized


def map_langgraph_event(event: dict[str, Any]) -> list[TokenEvent | ToolCallEvent | RetrievalEvent]:
    node_name = _extract_node_name(event)
    event_name = event.get("event")

    if event_name in TOKEN_EVENT_NAMES and node_name in FINAL_ANSWER_NODES:
        token = _extract_stream_token(event)
        if token:
            return [TokenEvent(content=token)]

    if event_name != "on_chain_end":
        return []

    output = _extract_output(event, node_name)
    if not output:
        return []

    if node_name == "planner_node":
        plan_payload = {
            "intent": output.get("intent"),
            "research_enabled": output.get("research_enabled"),
            "reasoning": output.get("planner_reasoning"),
            "sub_queries": output.get("sub_queries", []),
            "max_search_results": output.get("max_search_results"),
            "retrieval_limit": output.get("retrieval_limit"),
        }
        events: list[TokenEvent | ToolCallEvent | RetrievalEvent] = [
            ToolCallEvent(
                name="query_understanding",
                status="completed",
                payload=plan_payload,
            )
        ]

        queries = output.get("sub_queries")
        if isinstance(queries, list) and queries:
            events.append(
                ToolCallEvent(
                    name="search_queries",
                    status="generated",
                    payload={"queries": queries},
                )
            )
        return events

    if node_name == "search_node":
        search_results = output.get("search_results")
        if isinstance(search_results, list):
            url_count = 0
            query_labels: list[str] = []
            for result in search_results:
                if not isinstance(result, dict):
                    continue
                query_value = result.get("query")
                if isinstance(query_value, str):
                    query_labels.append(query_value)
                urls = result.get("urls")
                if isinstance(urls, list):
                    url_count += len([u for u in urls if isinstance(u, str) and u.strip()])

            return [
                ToolCallEvent(
                    name="web_search",
                    status="completed",
                    payload={
                        "query_count": len(query_labels),
                        "url_count": url_count,
                        "queries": query_labels,
                    },
                )
            ]

    if node_name == "document_intent_node":
        route_source = output.get("route_source")
        if isinstance(route_source, str):
            return [
                ToolCallEvent(
                    name="retrieval_route",
                    status="selected",
                    payload={
                        "route_source": route_source,
                        "reason": output.get("document_query_reason"),
                        "confidence": output.get("document_query_confidence"),
                    },
                )
            ]

    if node_name in {"retrieve_node", "document_retrieve_node", "hybrid_retrieve_node"}:
        documents = _normalize_documents(output.get("retrieved_documents"))
        if documents:
            return [RetrievalEvent(documents=documents)]

    return []


def extract_state_updates(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("event") != "on_chain_end":
        return {}

    node_name = _extract_node_name(event)
    output = _extract_output(event, node_name)
    if not output:
        return {}

    return {key: output[key] for key in FINAL_STATE_KEYS if key in output}

