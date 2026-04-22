from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UploadedFileMetadata(BaseModel):
    file_id: str
    filename: str
    session_id: str
    upload_timestamp: datetime
    chunk_count: int
    file_path: str | None = None


class UploadResponse(BaseModel):
    session_id: str
    files: list[UploadedFileMetadata]


class SessionFilesResponse(BaseModel):
    session_id: str
    files: list[UploadedFileMetadata]


class UploadedFileContentResponse(BaseModel):
    file_id: str
    filename: str
    session_id: str | None = None
    content: str
    chunk_count: int
    page_count: int = 0
    pages: list[dict[str, str | int]] = Field(default_factory=list)
    file_path: str | None = None


class DocumentRouteDecision(BaseModel):
    route_source: Literal["document", "web", "hybrid"] = "web"
    reason: str = Field(default="No uploaded documents available.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

