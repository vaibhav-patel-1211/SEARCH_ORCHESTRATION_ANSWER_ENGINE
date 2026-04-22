from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.services.document_ingestion import (
    delete_uploaded_file,
    get_uploaded_file_content,
    ingest_uploaded_files,
)
from database.local.client import (
    create_chat_session,
    get_or_create_default_session,
    get_session_by_id,
)
from schemas.document_schema import (
    UploadResponse,
    UploadedFileContentResponse,
    UploadedFileMetadata,
)
from utils.auth_utils import verify_access_token

router = APIRouter(tags=["Document Upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    session_id: str | None = Form(default=None),
    create_new_session: bool = Form(default=False),
    user_email: str = Depends(verify_access_token),
):
    if create_new_session:
        session = await create_chat_session(user_email, "New Chat")
    elif session_id:
        session = await get_session_by_id(session_id, user_email)
        if not session:
            session = await get_or_create_default_session(user_email)
    else:
        session = await get_or_create_default_session(user_email)

    resolved_session_id = str(session["_id"])
    ingested = await ingest_uploaded_files(
        uploaded_files=files,
        session_id=resolved_session_id,
        user_id=user_email,
    )

    return UploadResponse(
        session_id=resolved_session_id,
        files=[UploadedFileMetadata(**item) for item in ingested],
    )


@router.delete("/upload/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_uploaded_document(
    file_id: str,
    session_id: str | None = None,
    user_email: str = Depends(verify_access_token),
):
    removed = await delete_uploaded_file(
        file_id=file_id,
        user_id=user_email,
        session_id=session_id,
    )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found.",
        )

    return None


@router.get("/upload/{file_id}/content", response_model=UploadedFileContentResponse)
async def fetch_uploaded_document_content(
    file_id: str,
    session_id: str | None = None,
    user_email: str = Depends(verify_access_token),
):
    file_content = await get_uploaded_file_content(
        file_id=file_id,
        user_id=user_email,
        session_id=session_id,
    )
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found.",
        )

    return UploadedFileContentResponse(**file_content)

