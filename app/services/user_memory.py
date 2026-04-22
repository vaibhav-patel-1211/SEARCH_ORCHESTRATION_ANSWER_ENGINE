from __future__ import annotations

import re

from pydantic import BaseModel, Field

from config import model
from database.local.client import (
    get_memory_enabled,
    get_user_memories,
    upsert_user_memory,
)

MAX_MEMORIES_IN_PROMPT = 20


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
) -> list[dict]:
    if not await get_memory_enabled(user_id):
        return []

    prompt = (user_prompt or "").strip()
    if not prompt:
        return []

    extractor = model.with_structured_output(MemoryExtractionResult)
    system_prompt = (
        "Extract durable and useful user memories from the latest conversation turn.\n"
        "Only include stable personal preferences, profile details, goals, constraints, or recurring projects.\n"
        "Do not store temporary requests, one-off tasks, or generic topic questions.\n"
        "Return up to 5 items. If nothing useful exists, return an empty list."
    )

    try:
        extracted = await extractor.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"User prompt:\n{prompt}\n\n"
                        f"Assistant response:\n{assistant_response or ''}"
                    ),
                },
            ]
        )
    except Exception as exc:
        print(f"Memory extraction failed: {exc}")
        return []

    stored: list[dict] = []
    for item in extracted.items:
        key = _normalize_key(item.key)
        value = (item.value or "").strip()
        if not key or not value:
            continue
        if item.confidence < 0.55:
            continue
        stored_item = await upsert_user_memory(
            user_id=user_id,
            key=key,
            value=value,
            source_session_id=session_id,
            confidence=item.confidence,
        )
        stored.append(stored_item)

    return stored
