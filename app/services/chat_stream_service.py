"""
chat_stream_service.py - WebSocket streaming service.
Handles the real-time chat flow:
  1. Resolves/creates the chat session
  2. Runs the LangGraph pipeline with streaming enabled
  3. Maps internal LangGraph events to frontend-friendly WebSocket events
  4. Sends tokens, tool calls, and retrieval events as they happen
  5. At the end, sends a FinalAnswerEvent with metadata (intent, diagram, PDF, etc.)
  6. Saves messages and extracts user memories after completion

This is the primary way the React frontend communicates with the backend.
"""

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
    get_user_skills,
)
from graph.graph import graph
from graph.streaming import extract_state_updates, map_langgraph_event
from app.services.user_memory import (
    extract_and_store_user_memories,
    get_user_memory_context,
)
from app.services.skills import build_skill_context, match_skills
from schemas.ws_schema import ChatWebSocketRequest, FinalAnswerEvent, TokenEvent, ToolCallEvent

_background_tasks = set()

def _diagram_url(diagram_svg: str | None) -> str | None:
    """Convert internal diagram path to a URL the frontend can fetch."""
    if not diagram_svg:
        return None

    normalized = diagram_svg.replace("\\", "/")
    if normalized.startswith("/"):
        return normalized
    if normalized.startswith("static/"):
        return f"/{normalized}"
    return f"/static/{normalized}"


def _download_url(pdf_filename: str | None) -> str | None:
    """Build the download URL for a generated PDF."""
    if not pdf_filename:
        return None
    return f"/v1/download/{pdf_filename}"


async def _resolve_session(request: ChatWebSocketRequest, user_email: str) -> dict[str, Any]:
    """Find existing session or create a new one based on the request."""
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
    """
    Main streaming function. Yields WebSocket event dicts as the pipeline runs.
    The frontend receives these events and updates the UI progressively:
      - ToolCallEvent: shows "Planning...", "Searching...", etc.
      - TokenEvent: appends text to the streaming answer
      - RetrievalEvent: shows retrieved source documents
      - FinalAnswerEvent: signals completion with full metadata
    """
    query = request.query or ""
    if not query:
        raise ValueError("query is required")

    # Resolve session and save user message
    session = await _resolve_session(request, user_email)
    session_id = str(session["_id"])

    await add_message_to_session(session_id, user_email, "user", query)

    # Auto-title the session from the first message
    if len(session.get("messages", [])) == 0:
        title = query[:50] + "..." if len(query) > 50 else query
        await update_session_title(session_id, user_email, title)

    # Gather all context needed for the pipeline
    uploaded_files = await get_session_uploaded_files(session_id, user_email)
    memory_context = await get_user_memory_context(user_email)
    user_skills = await get_user_skills(user_email, limit=200)
    enabled_skills = [skill for skill in user_skills if skill.get("enabled", True)]

    # Match skills: use explicit skill_id if provided, otherwise auto-match by triggers
    if request.skill_id:
        matched_skills = [s for s in enabled_skills if s.get("id") == request.skill_id]
    else:
        matched_skills = match_skills(query, enabled_skills)
    skill_context = build_skill_context(matched_skills)

    # Build the input for the LangGraph pipeline
    graph_input = {
        "prompt": query,
        "research_enabled": request.research_enabled,
        "session_id": session_id,
        "user_id": user_email,
        "memory_context": memory_context,
        "skill_context": skill_context,
        "uploaded_files": uploaded_files,
        "messages": [HumanMessage(content=query)],
    }
    config = {"configurable": {"thread_id": session_id}}

    final_state: dict[str, Any] = {}
    token_buffer: list[str] = []
    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    # Notify frontend about matched skills
    if matched_skills:
        await event_queue.put(
            ToolCallEvent(
                name="skill_match",
                status="selected",
                payload={
                    "skills": [
                        {
                            "id": str(skill.get("id", "")),
                            "name": skill.get("name"),
                        }
                        for skill in matched_skills
                    ]
                },
            ).model_dump(exclude_none=True)
        )

    async def token_callback(token: str) -> None:
        """Called by answer nodes to stream each token to the WebSocket."""
        if not token:
            return
        await event_queue.put(TokenEvent(content=token).model_dump(exclude_none=True))

    config["configurable"]["token_callback"] = token_callback

    async def produce_graph_events() -> None:
        """Background task: runs the graph and pushes events to the queue."""
        async for raw_event in graph.astream_events(
            graph_input,
            config=config,
            version="v2",
        ):
            if not isinstance(raw_event, dict):
                continue

            # Accumulate final state values as they appear
            final_state.update(extract_state_updates(raw_event))

            # Map LangGraph events to our WebSocket protocol
            for stream_event in map_langgraph_event(raw_event):
                payload = stream_event.model_dump(exclude_none=True)
                # Skip token events here (they come via token_callback instead)
                if payload.get("type") == "token":
                    continue
                await event_queue.put(payload)

    # Start the graph execution as a background task
    producer_task = asyncio.create_task(produce_graph_events())

    try:
        # Consume events from the queue and yield them to the WebSocket
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

    # After streaming is done, save the assistant's response
    final_answer = final_state.get("final_answer") or "".join(token_buffer)
    if final_answer:
        await add_message_to_session(session_id, user_email, "assistant", final_answer)

        # Extract user memories from this conversation turn
        history_messages: list[dict[str, Any]] = []
        if isinstance(session.get("messages", []), list):
            for item in session.get("messages", []):
                if isinstance(item, dict):
                    history_messages.append(
                        {"role": item.get("role"), "content": item.get("content")}
                    )
        history_messages.append({"role": "user", "content": query})
        history_messages.append({"role": "assistant", "content": final_answer})
        task = asyncio.create_task(
            extract_and_store_user_memories(
                user_id=user_email,
                session_id=session_id,
                user_prompt=query,
                assistant_response=final_answer,
                chat_history=history_messages,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    # Send the final event with all metadata
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
