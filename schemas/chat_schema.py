from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

from schemas.document_schema import UploadedFileMetadata

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime


class ChatSession(BaseModel):
    id: str
    user_id: str
    title: str
    messages: List[Message]
    created_at: datetime
    updated_at: datetime


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"


class AddMessageRequest(BaseModel):
    role: str
    content: str


class UpdateTitleRequest(BaseModel):
    title: str


class ChatSessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    messages: List[Message]
    uploaded_files: List[UploadedFileMetadata] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    sessions: List[ChatSessionResponse]
    total: int

class OptimizePromptRequest(BaseModel):
    prompt: str

class OptimizePromptResponse(BaseModel):
    optimized_prompt: str

class SavedPrompt(BaseModel):
    id: str
    name: str
    content: str
    created_at: datetime

class CreateSavedPromptRequest(BaseModel):
    name: str
    content: str


class MemoryItem(BaseModel):
    id: str
    key: str
    value: str
    confidence: float | None = None
    source_session_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateMemoryRequest(BaseModel):
    key: str
    value: str


class MemoryListResponse(BaseModel):
    memories: List[MemoryItem]
    total: int


class MemorySettingsResponse(BaseModel):
    enabled: bool


class UpdateMemorySettingsRequest(BaseModel):
    enabled: bool


class Skill(BaseModel):
    id: str
    name: str
    description: str | None = None
    triggers: List[str] = Field(default_factory=list)
    prompt: str
    definition: str
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillListResponse(BaseModel):
    skills: List[Skill]
    total: int


class CreateSkillRequest(BaseModel):
    definition: str
    enabled: bool = True


class UpdateSkillRequest(BaseModel):
    definition: str | None = None
    enabled: bool | None = None
