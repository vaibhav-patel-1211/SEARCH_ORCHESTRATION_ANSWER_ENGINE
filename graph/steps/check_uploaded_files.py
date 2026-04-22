from __future__ import annotations


def check_uploaded_files_node(state):
    uploaded_files = state.get("uploaded_files", [])
    normalized_files = []

    for item in uploaded_files:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("file_id", "")).strip()
        filename = str(item.get("filename", "")).strip()
        if not file_id or not filename:
            continue
        normalized_files.append(
            {
                "file_id": file_id,
                "filename": filename,
                "session_id": str(item.get("session_id", "")).strip(),
                "upload_timestamp": item.get("upload_timestamp"),
                "chunk_count": item.get("chunk_count", 0),
            }
        )

    return {
        "uploaded_files": normalized_files,
        "uploaded_files_available": len(normalized_files) > 0,
    }

