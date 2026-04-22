from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatWebSocketRequest(BaseModel):
    type: Literal["start"] = "start"
    request_id: str | None = None
    query: str | None = None
    prompt: str | None = None
    research_enabled: bool = False
    session_id: str | None = None
    create_new_session: bool = False

    @model_validator(mode="after")
    def normalize_query(self) -> "ChatWebSocketRequest":
        value = (self.query or self.prompt or "").strip()
        if not value:
            raise ValueError("query is required")
        self.query = value
        return self


class CancelWebSocketRequest(BaseModel):
    type: Literal["cancel"] = "cancel"
    request_id: str | None = None


class RetrievedDocument(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    request_id: str | None = None
    content: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    request_id: str | None = None
    name: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RetrievalEvent(BaseModel):
    type: Literal["retrieval"] = "retrieval"
    request_id: str | None = None
    documents: list[RetrievedDocument]


class FinalAnswerEvent(BaseModel):
    type: Literal["final_answer"] = "final_answer"
    request_id: str | None = None
    content: str
    session_id: str | None = None
    intent: str | None = None
    active_files: list[str] | None = None
    diagram_url: str | None = None
    download_url: str | None = None
    cache_hit: bool = False


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    request_id: str | None = None
    message: str
    code: str | None = None
    details: dict[str, Any] | None = None

