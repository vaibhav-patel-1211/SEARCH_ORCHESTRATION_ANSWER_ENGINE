"""
main.py - FastAPI application entry point.
Sets up:
  - CORS middleware (allows frontend to call backend)
  - Static file serving (PDFs, diagrams, uploads)
  - Auth routes (signup/login)
  - Chat routes (sessions, messages, memory, skills)
  - WebSocket route (real-time streaming)
  - Upload route (document ingestion)
  - Main /v1/search endpoint (REST-based query processing)
  - PDF download endpoint

Can also run in CLI mode for local development testing.
"""

import asyncio
import os
import sys

# Fix for Playwright/Subprocess on Windows: NotImplementedError
# Windows needs ProactorEventLoop for subprocess support in asyncio
# This MUST be set before any event loop is created (including by FastAPI/Uvicorn).
if sys.platform == "win32":
    try:
        from asyncio import WindowsProactorEventLoopPolicy, set_event_loop_policy
        set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from langchain_core.messages import HumanMessage

from graph.graph import graph
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.ws_chat import router as ws_chat_router
from app.api.v1.upload import router as upload_router
from utils.auth_utils import verify_access_token
from database.local.client import (
    get_or_create_default_session,
    add_message_to_session,
    update_session_title,
    serialize_session,
    create_chat_session,
    get_session_by_id,
    get_session_uploaded_files,
)
from app.services.user_memory import (
    extract_and_store_user_memories,
    get_user_memory_context,
)
from app.services.skills import build_skill_context, match_skills

# ---------------- LIFESPAN ----------------
# Runs on startup and shutdown of the server

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create required directories on startup
    os.makedirs("static/reports", exist_ok=True)
    os.makedirs("static/diagram", exist_ok=True)
    os.makedirs("static/uploads", exist_ok=True)
    print("✅ Server started")
    yield
    print("🛑 Server shutting down")


# ---------------- APP ----------------

app = FastAPI(
    title="AI Search Orchestration Engine", version="1.0.0", lifespan=lifespan
)

# ---------------- CORS ----------------
# Allow all origins for development; restrict in production

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- STATIC FILES ----------------
# Serves PDFs, diagrams, and uploaded files

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- ROUTERS ----------------
# Each router handles a group of related endpoints

app.include_router(auth_router)      # /v1/auth/signup, /v1/auth/login
app.include_router(chat_router)      # /v1/chat/sessions, memory, skills
app.include_router(ws_chat_router)   # /ws/chat (WebSocket streaming)
app.include_router(upload_router)    # /upload (document ingestion)

# ---------------- REQUEST / RESPONSE SCHEMAS ----------------


class SearchRequest(BaseModel):
    prompt: str
    research_enabled: bool = False       # toggle from frontend (web search on/off)
    session_id: str | None = None        # existing chat session ID
    create_new_session: bool = False     # flag to start a new conversation


class SearchResponse(BaseModel):
    answer: str
    intent: str | None = None
    active_files: list[str] | None = None
    diagram_url: str | None = None       # path to diagram image if generated
    download_url: str | None = None      # path to PDF if generated
    session_id: str | None = None


# ---------------- AUTH DEPENDENCY ----------------

def get_current_user(token: str = Depends(verify_access_token)):
    """Verify JWT token and return user email."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing token"
        )
    return token


# ---------------- SEARCH ENDPOINT ----------------

@app.post("/v1/search", response_model=SearchResponse)
async def search(
    request: SearchRequest, 
    background_tasks: BackgroundTasks,
    user_email: str = Depends(verify_access_token)
):
    """
    Main REST search endpoint (alternative to WebSocket).
    Processes the query through the full LangGraph pipeline and returns the result.
    """
    try:
        # Resolve or create the chat session
        session = None

        if request.create_new_session:
            session = await create_chat_session(
                user_email,
                request.prompt[:50] if len(request.prompt) > 50 else request.prompt,
            )
        elif request.session_id:
            from database.local.client import get_session_by_id

            session = await get_session_by_id(request.session_id, user_email)
            if not session:
                session = await get_or_create_default_session(user_email)
        else:
            session = await get_or_create_default_session(user_email)

        session_id = str(session["_id"])

        # Save user message to session history
        await add_message_to_session(session_id, user_email, "user", request.prompt)

        # Auto-set session title from first message
        if len(session.get("messages", [])) == 0 and request.prompt:
            title = (
                request.prompt[:50] + "..."
                if len(request.prompt) > 50
                else request.prompt
            )
            await update_session_title(session_id, user_email, title)

        # Prepare graph input with all context
        config = {"configurable": {"thread_id": session_id}}
        uploaded_files = await get_session_uploaded_files(session_id, user_email)
        memory_context = await get_user_memory_context(user_email)
        from database.local.client import get_user_skills
        user_skills = await get_user_skills(user_email, limit=200)
        enabled_skills = [skill for skill in user_skills if skill.get("enabled", True)]
        matched_skills = match_skills(request.prompt, enabled_skills)
        skill_context = build_skill_context(matched_skills)

        # Run the full LangGraph pipeline
        result = await graph.ainvoke(
            {
                "prompt": request.prompt,
                "research_enabled": request.research_enabled,
                "session_id": session_id,
                "user_id": user_email,
                "memory_context": memory_context,
                "skill_context": skill_context,
                "uploaded_files": uploaded_files,
                "messages": [HumanMessage(content=request.prompt)],
            },
            config=config,
        )

        final_answer = result.get("final_answer", "")

        # Save assistant response to session
        await add_message_to_session(session_id, user_email, "assistant", final_answer)

        # Extract and store user memories from this conversation turn
        history_messages: list[dict[str, str]] = []
        if isinstance(session.get("messages", []), list):
            for item in session.get("messages", []):
                if isinstance(item, dict):
                    history_messages.append(
                        {"role": item.get("role", ""), "content": item.get("content", "")}
                    )
        history_messages.append({"role": "user", "content": request.prompt})
        history_messages.append({"role": "assistant", "content": final_answer})
        background_tasks.add_task(
            extract_and_store_user_memories,
            user_id=user_email,
            session_id=session_id,
            user_prompt=request.prompt,
            assistant_response=final_answer,
            chat_history=history_messages,
        )

        # Build response
        response = SearchResponse(
            answer=final_answer,
            intent=result.get("intent"),
            active_files=[
                str(item.get("filename", "")).strip()
                for item in uploaded_files
                if isinstance(item, dict) and str(item.get("filename", "")).strip()
            ] or None,
            session_id=session_id,
        )

        if result.get("diagram_svg"):
            diagram_svg = result["diagram_svg"].replace("\\", "/")
            if diagram_svg.startswith("static/"):
                response.diagram_url = f"/{diagram_svg}"
            else:
                response.diagram_url = f"/static/{diagram_svg}"

        if result.get("pdf_filename"):
            response.download_url = f"/v1/download/{result['pdf_filename']}"

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# ---------------- PDF DOWNLOAD ENDPOINT ----------------

@app.get("/v1/download/{filename}")
async def download_pdf(filename: str):
    """Serve a generated PDF report for download."""
    # Sanitize filename to prevent path traversal attacks
    safe_name = os.path.basename(filename)
    filepath = os.path.join("static", "reports", safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or already deleted",
        )

    return FileResponse(
        path=filepath,
        filename=safe_name,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_name}"},
    )


# ---------------- HEALTH CHECK ----------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------- CLI DEV RUNNER ----------------

async def cli_loop():
    """
    Local CLI chat loop for development testing without the HTTP server.
    Run with: python main.py --cli
    """
    import sys

    thread_id = "cli_session"
    print("CLI mode — type 'exit' to quit.\n")

    while True:
        user_input = input("\nUser: ").strip()
        if user_input.lower() in ["exit", "quit", "q"]:
            break
        if not user_input:
            continue

        result = await graph.ainvoke(
            {
                "prompt": user_input,
                "research_enabled": True,
                "messages": [HumanMessage(content=user_input)],
            },
            config={"configurable": {"thread_id": thread_id}},
        )

        # If the answer was cached, it won't stream, so print it here
        if result.get("cache_hit"):
            print("\n======= Cached Answer =======\n")
            print(result.get("final_answer", ""))
            print("\n======= Done =======\n")

        if result.get("pdf_filename"):
            print(f"\n📄 PDF: static/reports/{result['pdf_filename']}")
        if result.get("diagram_svg"):
            print(f"\n🖼  Diagram: {result['diagram_svg']}")


if __name__ == "__main__":
    import sys

    if "--cli" in sys.argv:
        asyncio.run(cli_loop())
    else:
        import uvicorn
        uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
