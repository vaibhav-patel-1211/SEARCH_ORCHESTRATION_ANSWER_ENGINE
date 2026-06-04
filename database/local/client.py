"""
client.py - MongoDB async client using Motor (async driver).
Manages all database operations for:
  - Chat sessions (CRUD, message history)
  - Uploaded file metadata
  - Saved prompts
  - User memories (long-term personalization)
  - User skills (custom instructions)

Uses a singleton pattern with loop detection to handle Uvicorn reloads.
"""

import asyncio
import os
import threading
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId
from bson.errors import InvalidId

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "Search_orchestration"

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set")

# Singleton state for the Motor client
_client: AsyncIOMotorClient | None = None
_db = None
_bound_loop: asyncio.AbstractEventLoop | None = None
_index_ready = False
_lock = threading.Lock()


def get_db():
    """
    Return a Motor database bound to the current running event loop.
    Recreates the client if the event loop changed (happens on Uvicorn reload).
    Thread-safe via lock.
    """
    global _client, _db, _bound_loop

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    with _lock:
        loop_changed = current_loop is not None and _bound_loop is not current_loop
        if _client is None or _db is None or loop_changed:
            if _client is not None:
                _client.close()
            _client = AsyncIOMotorClient(MONGO_URI)
            _db = _client[DB_NAME]
            _bound_loop = current_loop

    return _db


async def ensure_indexes():
    """Create MongoDB indexes on first call (idempotent). Speeds up queries."""
    global _index_ready
    if _index_ready:
        return

    db = get_db()
    await db.chat_sessions.create_index([("user_id", 1), ("updated_at", -1)])
    await db.uploaded_files.create_index([("user_id", 1), ("session_id", 1), ("upload_timestamp", -1)])
    await db.uploaded_files.create_index([("file_id", 1)], unique=True)
    await db.user_memories.create_index([("user_id", 1), ("updated_at", -1)])
    await db.user_memories.create_index([("user_id", 1), ("key", 1)], unique=True)
    await db.memory_settings.create_index([("user_id", 1)], unique=True)
    await db.user_skills.create_index([("user_id", 1), ("updated_at", -1)])
    _index_ready = True


# ── Chat Session Operations ──

async def create_chat_session(user_id: str, title: str = "New Chat"):
    """Create a new chat session for the user."""
    await ensure_indexes()
    db = get_db()

    session = {
        "user_id": user_id,
        "title": title,
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = await db.chat_sessions.insert_one(session)
    session["_id"] = result.inserted_id
    return session


async def get_user_sessions(user_id: str, skip: int = 0, limit: int = 50):
    """Get all sessions for a user, sorted by most recent first."""
    await ensure_indexes()
    db = get_db()

    sessions = (
        await db.chat_sessions.find({"user_id": user_id})
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    return sessions


async def get_session_by_id(session_id: str, user_id: str):
    """Fetch a specific session (validates ownership via user_id)."""
    db = get_db()
    try:
        session = await db.chat_sessions.find_one(
            {"_id": ObjectId(session_id), "user_id": user_id}
        )
        return session
    except:
        return None


async def add_message_to_session(
    session_id: str, user_id: str, role: str, content: str
):
    """Append a message to the session's message array."""
    db = get_db()
    message = {"role": role, "content": content, "timestamp": datetime.utcnow()}
    result = await db.chat_sessions.find_one_and_update(
        {"_id": ObjectId(session_id), "user_id": user_id},
        {"$push": {"messages": message}, "$set": {"updated_at": datetime.utcnow()}},
        return_document=True,
    )
    return result


async def update_session_title(session_id: str, user_id: str, title: str):
    db = get_db()
    result = await db.chat_sessions.find_one_and_update(
        {"_id": ObjectId(session_id), "user_id": user_id},
        {"$set": {"title": title, "updated_at": datetime.utcnow()}},
        return_document=True,
    )
    return result


async def delete_session(session_id: str, user_id: str):
    """Delete a session and its associated uploaded files metadata."""
    db = get_db()
    try:
        oid = ObjectId(session_id)
    except InvalidId:
        return False

    result = await db.chat_sessions.delete_one({"_id": oid, "user_id": user_id})
    await db.uploaded_files.delete_many({"session_id": session_id, "user_id": user_id})
    return result.deleted_count > 0


async def get_or_create_default_session(user_id: str):
    """Get the most recent session, or create one if none exist."""
    await ensure_indexes()
    db = get_db()

    session = await db.chat_sessions.find_one(
        {"user_id": user_id}, sort=[("updated_at", -1)]
    )
    if not session:
        session = await create_chat_session(user_id, "New Chat")
    return session


def serialize_session(session):
    """Convert ObjectId to string for JSON serialization."""
    if session:
        session["_id"] = str(session["_id"])
    return session


# ── Uploaded Files Operations ──

def _serialize_uploaded_file(doc: dict[str, Any]) -> dict[str, Any]:
    payload = dict(doc)
    payload.pop("_id", None)
    return payload


async def add_uploaded_file_metadata(
    session_id: str,
    user_id: str,
    file_metadata: dict[str, Any],
):
    """Store metadata about an uploaded file (upsert by file_id)."""
    await ensure_indexes()
    db = get_db()

    payload = {
        "file_id": file_metadata["file_id"],
        "filename": file_metadata["filename"],
        "session_id": session_id,
        "user_id": user_id,
        "upload_timestamp": file_metadata["upload_timestamp"],
        "chunk_count": file_metadata["chunk_count"],
        "file_path": file_metadata.get("file_path"),
    }

    await db.uploaded_files.update_one(
        {"file_id": payload["file_id"], "user_id": user_id},
        {"$set": payload},
        upsert=True,
    )

    return payload


async def get_session_uploaded_files(session_id: str, user_id: str) -> list[dict[str, Any]]:
    """Get all files uploaded in a specific session."""
    await ensure_indexes()
    db = get_db()

    files = (
        await db.uploaded_files.find({"session_id": session_id, "user_id": user_id})
        .sort("upload_timestamp", 1)
        .to_list(length=1000)
    )
    return [_serialize_uploaded_file(item) for item in files]


async def delete_uploaded_file_metadata(
    file_id: str,
    user_id: str,
    session_id: str | None = None,
) -> bool:
    await ensure_indexes()
    db = get_db()

    query: dict[str, Any] = {"file_id": file_id, "user_id": user_id}
    if session_id:
        query["session_id"] = session_id

    result = await db.uploaded_files.delete_one(query)
    return result.deleted_count > 0


# ── Saved Prompts Operations ──

async def create_saved_prompt(user_id: str, name: str, content: str):
    """Save a reusable prompt template (upsert by name)."""
    db = get_db()
    prompt = {
        "user_id": user_id,
        "name": name,
        "content": content,
        "created_at": datetime.utcnow(),
    }
    await db.saved_prompts.update_one(
        {"user_id": user_id, "name": name},
        {"$set": prompt},
        upsert=True,
    )
    return prompt


async def get_saved_prompts(user_id: str):
    db = get_db()
    prompts = await db.saved_prompts.find({"user_id": user_id}).to_list(length=100)
    for p in prompts:
        p["_id"] = str(p["_id"])
    return prompts


async def get_saved_prompt_by_name(user_id: str, name: str):
    db = get_db()
    prompt = await db.saved_prompts.find_one({"user_id": user_id, "name": name})
    if prompt:
        prompt["_id"] = str(prompt["_id"])
    return prompt


async def delete_saved_prompt(user_id: str, prompt_id: str):
    db = get_db()
    try:
        oid = ObjectId(prompt_id)
    except:
        return False
    result = await db.saved_prompts.delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count > 0


# ── User Memory Operations (long-term personalization) ──

def _serialize_user_memory(doc: dict[str, Any]) -> dict[str, Any]:
    payload = dict(doc)
    payload["id"] = str(payload.pop("_id", ""))
    return payload


async def get_memory_enabled(user_id: str) -> bool:
    """Check if user has memory feature enabled (default: True)."""
    await ensure_indexes()
    db = get_db()
    setting = await db.memory_settings.find_one({"user_id": user_id})
    if not setting:
        return True
    return bool(setting.get("enabled", True))


async def set_memory_enabled(user_id: str, enabled: bool) -> bool:
    await ensure_indexes()
    db = get_db()
    await db.memory_settings.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "enabled": bool(enabled),
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    return bool(enabled)


async def upsert_user_memory(
    user_id: str,
    key: str,
    value: str,
    *,
    source_session_id: str | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Store or update a memory fact (e.g., "user_name" -> "Alice")."""
    await ensure_indexes()
    db = get_db()
    now = datetime.utcnow()
    update_fields: dict[str, Any] = {
        "user_id": user_id,
        "key": key,
        "value": value,
        "updated_at": now,
    }
    if source_session_id:
        update_fields["source_session_id"] = source_session_id
    if confidence is not None:
        update_fields["confidence"] = float(confidence)

    await db.user_memories.update_one(
        {"user_id": user_id, "key": key},
        {"$set": update_fields, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    stored = await db.user_memories.find_one({"user_id": user_id, "key": key})
    if not stored:
        return {
            "id": "",
            "user_id": user_id,
            "key": key,
            "value": value,
            "source_session_id": source_session_id,
            "confidence": confidence,
            "created_at": now,
            "updated_at": now,
        }
    return _serialize_user_memory(stored)


async def get_user_memories(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    await ensure_indexes()
    db = get_db()
    items = (
        await db.user_memories.find({"user_id": user_id})
        .sort("updated_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )
    return [_serialize_user_memory(item) for item in items]


async def delete_user_memory(user_id: str, memory_id: str) -> bool:
    await ensure_indexes()
    db = get_db()
    try:
        oid = ObjectId(memory_id)
    except InvalidId:
        return False
    result = await db.user_memories.delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count > 0


async def clear_user_memories(user_id: str) -> int:
    """Delete all memories for a user (used by "clear all" button)."""
    await ensure_indexes()
    db = get_db()
    result = await db.user_memories.delete_many({"user_id": user_id})
    return int(result.deleted_count)


# ── User Skills Operations (custom instructions/behaviors) ──

def _serialize_user_skill(doc: dict[str, Any]) -> dict[str, Any]:
    payload = dict(doc)
    payload["id"] = str(payload.pop("_id", ""))
    return payload


async def get_user_skills(user_id: str, limit: int = 200) -> list[dict[str, Any]]:
    await ensure_indexes()
    db = get_db()
    items = (
        await db.user_skills.find({"user_id": user_id})
        .sort("updated_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )
    return [_serialize_user_skill(item) for item in items]


async def create_user_skill(user_id: str, skill: dict[str, Any]) -> dict[str, Any]:
    """Create a new skill with name, triggers, and prompt instructions."""
    await ensure_indexes()
    db = get_db()
    now = datetime.utcnow()
    payload = {
        "user_id": user_id,
        "name": skill.get("name"),
        "description": skill.get("description"),
        "triggers": skill.get("triggers", []),       # keywords that activate this skill
        "prompt": skill.get("prompt"),               # instructions for the LLM
        "definition": skill.get("definition", ""),
        "enabled": bool(skill.get("enabled", True)),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.user_skills.insert_one(payload)
    payload["_id"] = result.inserted_id
    return _serialize_user_skill(payload)


async def update_user_skill(
    user_id: str, skill_id: str, update_fields: dict[str, Any]
) -> dict[str, Any] | None:
    await ensure_indexes()
    db = get_db()
    try:
        oid = ObjectId(skill_id)
    except InvalidId:
        return None

    update_fields = dict(update_fields or {})
    update_fields["updated_at"] = datetime.utcnow()
    result = await db.user_skills.find_one_and_update(
        {"_id": oid, "user_id": user_id},
        {"$set": update_fields},
        return_document=True,
    )
    if not result:
        return None
    return _serialize_user_skill(result)


async def delete_user_skill(user_id: str, skill_id: str) -> bool:
    await ensure_indexes()
    db = get_db()
    try:
        oid = ObjectId(skill_id)
    except InvalidId:
        return False
    result = await db.user_skills.delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count > 0
