from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage

from database.local.client import (
    add_message_to_session,
    create_chat_session,
    get_or_create_default_session,
    get_session_by_id,
    get_session_uploaded_files,
    update_session_title,
)
from graph.graph import graph
from graph.streaming import extract_state_updates, map_langgraph_event
from app.services.user_memory import (
    extract_and_store_user_memories,
    get_user_memory_context,
)
from schemas.ws_schema import ChatWebSocketRequest, FinalAnswerEvent, TokenEvent


def _diagram_url(diagram_svg: str | None) -> str | None:
    if not diagram_svg:
        return None

    normalized = diagram_svg.replace("\\", "/")
    if normalized.startswith("/"):
        return normalized
    if normalized.startswith("static/"):
        return f"/{normalized}"
    return f"/static/{normalized}"


def _download_url(pdf_filename: str | None) -> str | None:
    if not pdf_filename:
        return None
    return f"/v1/download/{pdf_filename}"


async def _resolve_session(request: ChatWebSocketRequest, user_email: str) -> dict[str, Any]:
    query = request.query or ""

    if request.create_new_session:
        return await create_chat_session(
            user_email,
            query[:50] if len(query) > 50 else query,
        )

    if request.session_id:
        existing = await get_session_by_id(request.session_id, user_email)
        if existing:
            return existing

    return await get_or_create_default_session(user_email)


async def stream_chat_events(
    request: ChatWebSocketRequest,
    user_email: str,
) -> AsyncIterator[dict[str, Any]]:
    query = request.query or ""
    if not query:
        raise ValueError("query is required")

    session = await _resolve_session(request, user_email)
    session_id = str(session["_id"])

    await add_message_to_session(session_id, user_email, "user", query)

    if len(session.get("messages", [])) == 0:
        title = query[:50] + "..." if len(query) > 50 else query
        await update_session_title(session_id, user_email, title)
    uploaded_files = await get_session_uploaded_files(session_id, user_email)
    memory_context = await get_user_memory_context(user_email)

    graph_input = {
        "prompt": query,
        "research_enabled": request.research_enabled,
        "session_id": session_id,
        "user_id": user_email,
        "memory_context": memory_context,
        "uploaded_files": uploaded_files,
        "messages": [HumanMessage(content=query)],
    }
    config = {"configurable": {"thread_id": session_id}}

    final_state: dict[str, Any] = {}
    token_buffer: list[str] = []
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def token_callback(token: str) -> None:
        if not token:
            return
        await event_queue.put(TokenEvent(content=token).model_dump(exclude_none=True))

    config["configurable"]["token_callback"] = token_callback

    async def produce_graph_events() -> None:
        async for raw_event in graph.astream_events(
            graph_input,
            config=config,
            version="v2",
        ):
            if not isinstance(raw_event, dict):
                continue

            final_state.update(extract_state_updates(raw_event))

            for stream_event in map_langgraph_event(raw_event):
                payload = stream_event.model_dump(exclude_none=True)
                if payload.get("type") == "token":
                    continue
                await event_queue.put(payload)

    producer_task = asyncio.create_task(produce_graph_events())

    try:
        while True:
            if producer_task.done() and event_queue.empty():
                break

            try:
                payload = await asyncio.wait_for(event_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if payload.get("type") == "token":
                token_buffer.append(payload.get("content", ""))
            yield payload

        await producer_task
    except asyncio.CancelledError:
        producer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer_task
        raise
    except Exception:
        producer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await producer_task
        raise

    final_answer = final_state.get("final_answer") or "".join(token_buffer)
    if final_answer:
        await add_message_to_session(session_id, user_email, "assistant", final_answer)
        await extract_and_store_user_memories(
            user_id=user_email,
            session_id=session_id,
            user_prompt=query,
            assistant_response=final_answer,
        )

    final_event = FinalAnswerEvent(
        content=final_answer,
        session_id=session_id,
        intent=final_state.get("intent"),
        active_files=[
            str(item.get("filename", "")).strip()
            for item in uploaded_files
            if isinstance(item, dict) and str(item.get("filename", "")).strip()
        ] or None,
        diagram_url=_diagram_url(final_state.get("diagram_svg")),
        download_url=_download_url(final_state.get("pdf_filename")),
        cache_hit=bool(final_state.get("cache_hit", False)),
    )
    yield final_event.model_dump(exclude_none=True)

