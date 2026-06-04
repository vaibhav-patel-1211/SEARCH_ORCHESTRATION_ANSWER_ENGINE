"""
document_ingestion.py - Handles file upload and processing pipeline.
Supports PDF, DOCX, and TXT files.
Flow:
  1. Read and extract text from uploaded file
  2. Split text into chunks (1200 chars with 200 overlap)
  3. Generate embeddings for each chunk
  4. Store chunks + embeddings in MongoDB Atlas (for vector search)
  5. Save file metadata to local DB
  6. Save original file to static/uploads/

Also provides functions to retrieve file content and delete uploaded files.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
from datetime import datetime
from uuid import uuid4

from docx import Document
from fastapi import HTTPException, UploadFile, status
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pymongo.errors import BulkWriteError

from config import embedding_model
from database.cloud.mongo_atlas_setup import uploaded_document_chunks
from database.local.client import add_uploaded_file_metadata, delete_uploaded_file_metadata

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
CHUNK_SIZE = 1200       # characters per chunk
CHUNK_OVERLAP = 200     # overlap between consecutive chunks (preserves context)


# ── Text extraction functions (one per file type) ──

def _read_pages_from_pdf(file_bytes: bytes) -> list[str]:
    """Extract text from each page of a PDF separately (preserves page numbers)."""
    reader = PdfReader(io.BytesIO(file_bytes))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def _read_text_from_pdf(file_bytes: bytes) -> str:
    pages = _read_pages_from_pdf(file_bytes)
    return "\n".join(pages).strip()


def _read_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX by reading all paragraphs."""
    document = Document(io.BytesIO(file_bytes))
    lines = [para.text.strip() for para in document.paragraphs if para.text.strip()]
    return "\n".join(lines).strip()


def _read_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore").strip()


def _extract_text(filename: str, file_bytes: bytes) -> str:
    """Route to the correct extractor based on file extension."""
    extension = os.path.splitext(filename.lower())[1]
    if extension == ".pdf":
        return _read_text_from_pdf(file_bytes)
    if extension == ".docx":
        return _read_text_from_docx(file_bytes)
    if extension == ".txt":
        return _read_text_from_txt(file_bytes)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported file type: {extension}. Allowed: PDF, DOCX, TXT.",
    )


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks using LangChain's recursive splitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(text)


def _build_chunk_documents(
    *,
    file_id: str,
    filename: str,
    session_id: str,
    user_id: str,
    upload_timestamp: datetime,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> list[dict]:
    """Build MongoDB documents for each chunk (with embedding vector)."""
    records: list[dict] = []
    for index, (chunk_item, vector) in enumerate(zip(chunks, embeddings)):
        chunk = str(chunk_item.get("text") or "").strip()
        page_number = chunk_item.get("page_number")
        # Use MD5 of file_id + index + text as unique chunk ID
        chunk_id = hashlib.md5(f"{file_id}:{index}:{chunk}".encode("utf-8")).hexdigest()
        payload = {
            "_id": chunk_id,
            "file_id": file_id,
            "filename": filename,
            "session_id": session_id,
            "user_id": user_id,
            "upload_timestamp": upload_timestamp,
            "chunk_index": index,
            "text": chunk,
            "embedding": vector,
            "source_type": "uploaded_document",
        }
        if isinstance(page_number, int):
            payload["page_number"] = page_number
        records.append(payload)
    return records


def _merge_chunk_sequence(chunks: list[str]) -> str:
    """
    Merge overlapping chunks back into continuous text.
    Detects overlap between consecutive chunks and removes duplicated portions.
    """
    if not chunks:
        return ""

    merged = chunks[0].strip()
    for part in chunks[1:]:
        candidate = part.strip()
        if not candidate:
            continue

        # Find the longest suffix of merged that matches a prefix of candidate
        max_overlap = min(len(merged), len(candidate), CHUNK_OVERLAP * 2)
        overlap = 0
        for size in range(max_overlap, 0, -1):
            if merged.endswith(candidate[:size]):
                overlap = size
                break

        merged = f"{merged}{candidate[overlap:]}"

    return merged.strip()


# ── Main ingestion function ──

async def ingest_uploaded_file(
    *,
    uploaded_file: UploadFile,
    session_id: str,
    user_id: str,
) -> dict:
    """
    Full ingestion pipeline for a single file:
    validate -> extract text -> chunk -> embed -> store in MongoDB -> save metadata
    """
    filename = (uploaded_file.filename or "").strip()
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    extension = os.path.splitext(filename.lower())[1]
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {extension}. Allowed: PDF, DOCX, TXT.",
        )

    file_bytes = await uploaded_file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{filename}' is empty.",
        )

    # Extract and chunk the text (PDFs preserve page numbers)
    chunks: list[dict] = []

    if extension == ".pdf":
        pages = await asyncio.to_thread(_read_pages_from_pdf, file_bytes)
        for page_number, page_text in enumerate(pages, start=1):
            clean_page = str(page_text or "").strip()
            if not clean_page:
                continue
            page_chunks = await asyncio.to_thread(_chunk_text, clean_page)
            for chunk in page_chunks:
                if chunk.strip():
                    chunks.append({"text": chunk, "page_number": page_number})
    else:
        extracted_text = await asyncio.to_thread(_extract_text, filename, file_bytes)
        if not extracted_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not extract text from '{filename}'.",
            )
        raw_chunks = await asyncio.to_thread(_chunk_text, extracted_text)
        chunks = [{"text": chunk} for chunk in raw_chunks if str(chunk).strip()]

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No usable text chunks extracted from '{filename}'.",
        )

    # Generate embeddings for all chunks (batch operation)
    chunk_texts = [str(item.get("text") or "") for item in chunks]
    embeddings = await asyncio.to_thread(embedding_model.embed_documents, chunk_texts)
    if not embeddings:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed for '{filename}'.",
        )

    file_id = uuid4().hex
    upload_timestamp = datetime.utcnow()

    # Save original file to disk (for preview/download later)
    static_uploads_dir = os.path.join("static", "uploads")
    os.makedirs(static_uploads_dir, exist_ok=True)
    file_path = f"static/uploads/{file_id}{extension}"
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Store chunks with embeddings in MongoDB Atlas (for vector search)
    records = _build_chunk_documents(
        file_id=file_id,
        filename=filename,
        session_id=session_id,
        user_id=user_id,
        upload_timestamp=upload_timestamp,
        chunks=chunks,
        embeddings=embeddings,
    )

    try:
        uploaded_document_chunks.insert_many(records, ordered=False)
    except BulkWriteError:
        pass  # ignore duplicate key errors (idempotent)

    # Save metadata to local DB (for listing files in UI)
    metadata = {
        "file_id": file_id,
        "filename": filename,
        "upload_timestamp": upload_timestamp,
        "chunk_count": len(records),
        "file_path": file_path,
    }
    await add_uploaded_file_metadata(session_id, user_id, metadata)
    return {**metadata, "session_id": session_id}


async def ingest_uploaded_files(
    *,
    uploaded_files: list[UploadFile],
    session_id: str,
    user_id: str,
) -> list[dict]:
    """Process multiple files sequentially."""
    ingested: list[dict] = []
    for uploaded_file in uploaded_files:
        ingested.append(
            await ingest_uploaded_file(
                uploaded_file=uploaded_file,
                session_id=session_id,
                user_id=user_id,
            )
        )
    return ingested


async def delete_uploaded_file(
    *,
    file_id: str,
    user_id: str,
    session_id: str | None = None,
) -> bool:
    """Delete file from disk, metadata DB, and vector store."""
    from database.local.client import get_db
    db = get_db()
    metadata = await db.uploaded_files.find_one({"file_id": file_id, "user_id": user_id})
    if metadata and metadata.get("file_path"):
        try:
            if os.path.exists(metadata["file_path"]):
                os.remove(metadata["file_path"])
        except Exception as e:
            print(f"Error deleting file {metadata['file_path']}: {e}")

    metadata_deleted = await delete_uploaded_file_metadata(
        file_id=file_id,
        user_id=user_id,
        session_id=session_id,
    )

    # Remove chunks from MongoDB Atlas vector store
    delete_filter = {"file_id": file_id, "user_id": user_id}
    if session_id:
        delete_filter["session_id"] = session_id

    delete_result = await asyncio.to_thread(uploaded_document_chunks.delete_many, delete_filter)
    return metadata_deleted or bool(delete_result.deleted_count)


def _load_uploaded_file_chunks(
    *,
    file_id: str,
    user_id: str,
    session_id: str | None = None,
) -> list[dict]:
    """Load all chunks for a file from MongoDB (sorted by chunk_index)."""
    query = {"file_id": file_id, "user_id": user_id}
    if session_id:
        query["session_id"] = session_id

    return list(
        uploaded_document_chunks.find(
            query,
            {
                "_id": 0,
                "file_id": 1,
                "filename": 1,
                "session_id": 1,
                "chunk_index": 1,
                "page_number": 1,
                "text": 1,
            },
        ).sort("chunk_index", 1)
    )


async def get_uploaded_file_content(
    *,
    file_id: str,
    user_id: str,
    session_id: str | None = None,
) -> dict | None:
    """
    Reconstruct the full file content from stored chunks.
    For PDFs, groups chunks by page number and merges overlapping text.
    """
    chunks = await asyncio.to_thread(
        _load_uploaded_file_chunks,
        file_id=file_id,
        user_id=user_id,
        session_id=session_id,
    )
    if not chunks:
        from database.local.client import get_db
        db = get_db()
        metadata = await db.uploaded_files.find_one({"file_id": file_id, "user_id": user_id})
        if not metadata:
            return None
        return {
            "file_id": file_id,
            "filename": metadata["filename"],
            "session_id": metadata["session_id"],
            "content": "",
            "chunk_count": metadata["chunk_count"],
            "page_count": 0,
            "pages": [],
            "file_path": metadata.get("file_path"),
        }

    filename = str(chunks[0].get("filename") or "Uploaded Document")
    resolved_session_id = str(chunks[0].get("session_id") or session_id or "")
    extension = os.path.splitext(filename.lower())[1]

    from database.local.client import get_db
    db = get_db()
    metadata = await db.uploaded_files.find_one({"file_id": file_id, "user_id": user_id})
    file_path = metadata.get("file_path") if metadata else None

    # For PDFs, reconstruct page-by-page
    pages: list[dict] = []
    if extension == ".pdf":
        page_map: dict[int, list[str]] = {}
        for item in chunks:
            page_number = item.get("page_number")
            text = str(item.get("text") or "").strip()
            if not isinstance(page_number, int) or not text:
                continue
            page_map.setdefault(page_number, []).append(text)

        for page_number in sorted(page_map.keys()):
            merged_text = _merge_chunk_sequence(page_map[page_number])
            if not merged_text:
                continue
            pages.append({"page_number": page_number, "content": merged_text})

    if pages:
        content = "\n\n".join(
            f"Page {int(page['page_number'])}\n{str(page['content'])}" for page in pages
        )
    else:
        content_parts = [str(item.get("text") or "").strip() for item in chunks]
        content = _merge_chunk_sequence([part for part in content_parts if part])

    return {
        "file_id": file_id,
        "filename": filename,
        "session_id": resolved_session_id or None,
        "content": content,
        "chunk_count": len(chunks),
        "page_count": len(pages),
        "pages": pages,
        "file_path": file_path,
    }
