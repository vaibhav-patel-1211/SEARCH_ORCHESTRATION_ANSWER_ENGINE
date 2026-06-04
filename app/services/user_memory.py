from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from config import model
from database.local.client import (
    get_memory_enabled,
    get_user_memories,
    upsert_user_memory,
)

MAX_MEMORIES_IN_PROMPT = 20
MAX_HISTORY_MESSAGES = 12


class ExtractedMemoryItem(BaseModel):
    key: str = Field(description="Short snake_case memory key, e.g. user_name")
    value: str = Field(description="Useful user fact value")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class MemoryExtractionResult(BaseModel):
    items: list[ExtractedMemoryItem] = Field(default_factory=list)


def _normalize_key(raw_key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (raw_key or "").strip().lower())
    normalized = normalized.strip("_")
    return normalized[:80]


def _format_memory_context(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = []
    for item in memories[:MAX_MEMORIES_IN_PROMPT]:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", "")).strip()
        if not key or not value:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _format_chat_history(history: list[dict]) -> str:
    if not history:
        return ""
    lines: list[str] = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _extract_json_payload(raw: str) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start_obj = cleaned.find("{")
    end_obj = cleaned.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        return cleaned[start_obj : end_obj + 1]

    start_list = cleaned.find("[")
    end_list = cleaned.rfind("]")
    if start_list != -1 and end_list != -1 and end_list > start_list:
        return cleaned[start_list : end_list + 1]

    return None


def _parse_memory_result(raw: str) -> MemoryExtractionResult:
    payload = _extract_json_payload(raw) or ""
    if not payload:
        return MemoryExtractionResult()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return MemoryExtractionResult()

    if isinstance(data, list):
        data = {"items": data}
    if not isinstance(data, dict):
        return MemoryExtractionResult()

    try:
        return MemoryExtractionResult.model_validate(data)
    except ValidationError:
        return MemoryExtractionResult()


async def get_user_memory_context(user_id: str) -> str:
    if not await get_memory_enabled(user_id):
        return ""
    memories = await get_user_memories(user_id, limit=MAX_MEMORIES_IN_PROMPT)
    return _format_memory_context(memories)


async def extract_and_store_user_memories(
    *,
    user_id: str,
    session_id: str,
    user_prompt: str,
    assistant_response: str,
    chat_history: list[dict] | None = None,
) -> list[dict]:
    if not await get_memory_enabled(user_id):
        return []

    prompt = (user_prompt or "").strip()
    history_text = _format_chat_history(chat_history or [])
    if not prompt and not history_text:
        return []

    system_prompt = (
        "Extract durable, highly detailed, and contextual user memories from the conversation.\n"
        "Ensure each extracted fact contains enough context so that another AI reading it independently can fully understand the user's situation, requirements, or preferences.\n"
        "Include explicit personal details, technical preferences (tools, frameworks, tone, stack), "
        "constraints, architectural decisions, and recurring projects.\n"
        "Do not store temporary requests, one-off tasks, or generic topic questions.\n"
        "Provide a detailed, self-contained description in the 'value' field.\n"
        "Return up to 6 items. If nothing useful exists, return an empty list."
    )

    try:
        structured_llm = model.with_structured_output(MemoryExtractionResult)
        extracted = await structured_llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Conversation history:\n{history_text}\n\n"
                        f"Latest user prompt:\n{prompt}\n\n"
                        f"Latest assistant response:\n{assistant_response or ''}"
                    ),
                },
            ]
        )
    except Exception as exc:
        print(f"Memory extraction failed: {exc}")
        return []

    stored: list[dict] = []
    if not extracted or not hasattr(extracted, "items"):
        return []
        
    for item in extracted.items:
        key = _normalize_key(item.key)
        value = (item.value or "").strip()
        if not key or not value:
            continue
        if item.confidence < 0.45:
            continue
        value = value[:1024].strip()
        stored_item = await upsert_user_memory(
            user_id=user_id,
            key=key,
            value=value,
            source_session_id=session_id,
            confidence=item.confidence,
        )
        stored.append(stored_item)

    return stored
