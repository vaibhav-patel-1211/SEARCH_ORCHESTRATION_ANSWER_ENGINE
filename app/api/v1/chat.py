from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from schemas.chat_schema import (
    CreateSessionRequest,
    AddMessageRequest,
    UpdateTitleRequest,
    ChatSessionResponse,
    SessionListResponse,
    Message,
    OptimizePromptRequest,
    OptimizePromptResponse,
    SavedPrompt,
    CreateSavedPromptRequest,
    MemoryItem,
    MemoryListResponse,
    MemorySettingsResponse,
    UpdateMemorySettingsRequest,
)
from schemas.document_schema import SessionFilesResponse, UploadedFileMetadata
from database.local.client import (
    get_db,
    create_chat_session,
    get_user_sessions,
    get_session_by_id,
    add_message_to_session,
    update_session_title,
    delete_session,
    serialize_session,
    get_session_uploaded_files,
    create_saved_prompt,
    get_saved_prompts,
    delete_saved_prompt,
    get_memory_enabled,
    set_memory_enabled,
    get_user_memories,
    delete_user_memory,
    clear_user_memories,
)
from utils.auth_utils import verify_access_token
from config import model

router = APIRouter(prefix="/v1/chat", tags=["Chat"])


def get_current_user_email(token: str = Depends(verify_access_token)):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token"
        )
    return token


@router.post("/optimize-prompt", response_model=OptimizePromptResponse)
async def optimize_prompt(
    request: OptimizePromptRequest, user_email: str = Depends(get_current_user_email)
):
    system_prompt = (
        "You are an expert prompt engineer. Your task is to take a simple prompt "
        "and transform it into a high-quality, detailed, and effective prompt "
        "that will yield better results from an AI. Provide only the optimized prompt text."
    )
    
    try:
        response = await model.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.prompt}
        ])
        return OptimizePromptResponse(optimized_prompt=response.content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prompt optimization failed: {str(e)}"
        )


@router.post(
    "/sessions", status_code=status.HTTP_201_CREATED, response_model=ChatSessionResponse
)
async def create_session(
    request: CreateSessionRequest, user_email: str = Depends(get_current_user_email)
):
    session = await create_chat_session(user_email, request.title)
    return ChatSessionResponse(
        id=str(session["_id"]),
        user_id=session["user_id"],
        title=session["title"],
        messages=[],
        uploaded_files=[],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    skip: int = 0, limit: int = 50, user_email: str = Depends(get_current_user_email)
):
    sessions = await get_user_sessions(user_email, skip, limit)
    total = len(sessions)

    session_responses = []
    for s in sessions:
        uploaded_files = await get_session_uploaded_files(str(s["_id"]), user_email)
        session_responses.append(
            ChatSessionResponse(
                id=str(s["_id"]),
                user_id=s["user_id"],
                title=s["title"],
                messages=[Message(**m) for m in s.get("messages", [])],
                uploaded_files=[UploadedFileMetadata(**item) for item in uploaded_files],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
            )
        )

    return SessionListResponse(sessions=session_responses, total=total)


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: str, user_email: str = Depends(get_current_user_email)
):
    session = await get_session_by_id(session_id, user_email)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    uploaded_files = await get_session_uploaded_files(session_id, user_email)

    return ChatSessionResponse(
        id=str(session["_id"]),
        user_id=session["user_id"],
        title=session["title"],
        messages=[Message(**m) for m in session.get("messages", [])],
        uploaded_files=[UploadedFileMetadata(**item) for item in uploaded_files],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


@router.put("/sessions/{session_id}/title", response_model=ChatSessionResponse)
async def update_title(
    session_id: str,
    request: UpdateTitleRequest,
    user_email: str = Depends(get_current_user_email),
):
    session = await update_session_title(session_id, user_email, request.title)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    uploaded_files = await get_session_uploaded_files(session_id, user_email)

    return ChatSessionResponse(
        id=str(session["_id"]),
        user_id=session["user_id"],
        title=session["title"],
        messages=[Message(**m) for m in session.get("messages", [])],
        uploaded_files=[UploadedFileMetadata(**item) for item in uploaded_files],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str, user_email: str = Depends(get_current_user_email)
):
    deleted = await delete_session(session_id, user_email)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return None


@router.get("/sessions/{session_id}/files", response_model=SessionFilesResponse)
async def get_session_files(
    session_id: str,
    user_email: str = Depends(get_current_user_email),
):
    session = await get_session_by_id(session_id, user_email)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    files = await get_session_uploaded_files(session_id, user_email)
    return SessionFilesResponse(
        session_id=session_id,
        files=[UploadedFileMetadata(**item) for item in files],
    )


@router.post("/saved-prompts", response_model=SavedPrompt)
async def create_prompt(
    request: CreateSavedPromptRequest, user_email: str = Depends(get_current_user_email)
):
    prompt = await create_saved_prompt(user_email, request.name, request.content)
    return SavedPrompt(
        id=str(prompt.get("_id", "")),
        name=prompt["name"],
        content=prompt["content"],
        created_at=prompt["created_at"],
    )


@router.get("/saved-prompts", response_model=List[SavedPrompt])
async def list_prompts(user_email: str = Depends(get_current_user_email)):
    prompts = await get_saved_prompts(user_email)
    return [
        SavedPrompt(
            id=str(p["_id"]),
            name=p["name"],
            content=p["content"],
            created_at=p["created_at"],
        )
        for p in prompts
    ]


@router.delete("/saved-prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: str, user_email: str = Depends(get_current_user_email)
):
    deleted = await delete_saved_prompt(user_email, prompt_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found"
        )
    return None


@router.get("/memory/settings", response_model=MemorySettingsResponse)
async def get_memory_settings(user_email: str = Depends(get_current_user_email)):
    enabled = await get_memory_enabled(user_email)
    return MemorySettingsResponse(enabled=enabled)


@router.put("/memory/settings", response_model=MemorySettingsResponse)
async def update_memory_settings(
    request: UpdateMemorySettingsRequest,
    user_email: str = Depends(get_current_user_email),
):
    enabled = await set_memory_enabled(user_email, request.enabled)
    return MemorySettingsResponse(enabled=enabled)


@router.get("/memory", response_model=MemoryListResponse)
async def list_memories(user_email: str = Depends(get_current_user_email)):
    memories = await get_user_memories(user_email, limit=200)
    return MemoryListResponse(
        memories=[MemoryItem(**item) for item in memories],
        total=len(memories),
    )


@router.delete("/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_item(
    memory_id: str,
    user_email: str = Depends(get_current_user_email),
):
    deleted = await delete_user_memory(user_email, memory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory item not found",
        )
    return None


@router.delete("/memory", status_code=status.HTTP_204_NO_CONTENT)
async def clear_memories(user_email: str = Depends(get_current_user_email)):
    await clear_user_memories(user_email)
    return None
