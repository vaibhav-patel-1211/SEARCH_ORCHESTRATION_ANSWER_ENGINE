"""
graph.py - The main LangGraph orchestration file.
Defines the state machine (StateGraph) that controls the entire query pipeline:
  START -> check files -> cache check -> document intent -> planner -> (route to nodes) -> END

Each node is a step in the pipeline (search, retrieve, code, diagram, answer, etc.)
Conditional edges route the query based on intent detected by the planner.
"""

import asyncio
import inspect
from typing import Annotated, List, TypedDict
import uuid
import re
import json

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

# ---------------- IMPORTS ----------------
# Each step is a separate module for clean separation of concerns

from app.api.diagram_generator import generate_diagram
from .steps.check_uploaded_files import check_uploaded_files_node
from .steps.document_intent import document_intent_node
from .steps.planner import planner_node
from .steps.cache_check import cache_check_node, get_answer_cache_key

from .steps.search import orchestrated_search_async
from .steps.clean_text import clean_multiple_urls
from .steps.chunking import chunk_text_node
from .steps.store_embeddings import embed_and_store_node

from .steps.embed_queries import embed_queries_node
from .steps.retrieve_chunks import retrieve_chunks_node
from .steps.retrieve_uploaded_chunks import retrieve_uploaded_chunks_node

from .steps.generate_answer import answer_node
from .steps.coding import coding_node
from .steps.generate_pdf import generate_pdf_node

from config import model, valkey

from langgraph.graph.message import add_messages

# ---------------- STATE ----------------
# This TypedDict defines ALL the data that flows through the graph.
# Each node reads from and writes to this shared state dict.

class State(TypedDict, total=False):
    prompt: str
    memory_context: str                # user's long-term memory (preferences, name, etc.)
    skill_context: str                 # active skill instructions to apply
    session_id: str
    user_id: str
    intent: str                        # detected intent: general, research, coding, diagram, pdf
    research_enabled: bool             # whether user toggled web search on
    route_source: str                  # "web", "document", or "hybrid"
    document_query_reason: str
    document_query_confidence: float
    uploaded_files: List[dict]
    uploaded_files_available: bool

    # Planner decides these dynamically based on query complexity
    max_search_results: int            # how many URLs to fetch per sub-query
    retrieval_limit: int               # how many chunks to retrieve from vector DB

    sub_queries: List[str]             # planner breaks complex queries into sub-queries
    planner_reasoning: str
    search_results: list               # raw search results from DuckDuckGo
    clean_text: dict                   # scraped + cleaned web page content
    chunks: List[str]                  # text split into chunks for embedding
    chunks_with_meta: List[dict]

    query_embeddings: List[list]       # vector embeddings of sub-queries
    retrieved_chunks: List[str]        # final chunks after retrieval + reranking
    retrieved_documents: List[dict]    # metadata about retrieved sources

    diagram_code: str                  # mermaid.js code for diagram
    diagram_svg: str                   # path to rendered diagram image

    rag_done: bool                     # flag: retrieval pipeline finished
    diagram_done: bool                 # flag: diagram generation finished

    final_answer: str                  # the final response sent to user
    messages: Annotated[List[BaseMessage], add_messages]  # chat history (LangGraph manages appending)

    # PDF output fields
    pdf_path: str
    pdf_filename: str
    cache_hit: bool                    # whether answer was served from cache

# ---------------- HELPERS ----------------

def sanitize_mermaid(code: str):
    """Clean up LLM-generated mermaid code to avoid rendering errors."""
    # Remove markdown blocks
    code = re.sub(r"```(?:mermaid)?", "", code)
    code = code.replace("```", "").strip()

    # Replace non-breaking hyphens (Unicode \u2011) with standard hyphens
    code = code.replace("\u2011", "-")

    # Remove styling and class definitions which often cause version-specific errors
    code = re.sub(r"classDef.*", "", code)
    code = re.sub(r"class\s.*", "", code)

    # Ensure it starts with graph TD
    if not code.startswith("graph"):
        code = "graph TD\n" + code

    return code

# ---------------- GENERAL CHAT NODE ----------------
# Handles simple conversational queries that don't need search/RAG

async def general_answer_node(state: State, config=None):
    messages = state.get("messages", [])
    research_enabled = bool(state.get("research_enabled", False))
    intent = state.get("intent", "general")
    memory_context = (state.get("memory_context") or "").strip()
    skill_context = (state.get("skill_context") or "").strip()

    # Build system message with optional memory and skill context
    memory_guidance = ""
    if memory_context:
        memory_guidance = (
            "\nPrivate memory context (for personalization; do not reveal as metadata):\n"
            f"{memory_context}\n"
            "Use this only when relevant."
        )
    skill_guidance = ""
    if skill_context:
        skill_guidance = (
            "\nActive skill instructions (apply when relevant):\n"
            f"{skill_context}\n"
        )

    if not research_enabled and intent != "general":
      system_msg = (
          "You are a friendly conversational AI assistant.\n"
          "Rules:\n"
          "- Respond naturally like a human\n"
          "- Provide complete and helpful responses\n"
          "- Remember personal details the user shares (like their name)\n"
          "- When appropriate, provide detailed explanations\n"
      ) + memory_guidance + skill_guidance
    else :
      system_msg = (
            "You are a friendly conversational AI assistant.\n"
            "Rules:\n"
            "- Respond naturally like a human\n"
            "- Provide complete and helpful responses\n"
            "- Remember personal details the user shares (like their name)\n"
            "- When appropriate, provide detailed explanations\n"
      ) + memory_guidance + skill_guidance

    # Format the full conversation history for the LLM
    formatted: list[BaseMessage] = [SystemMessage(content=system_msg)]
    for message in messages:
        if isinstance(message, HumanMessage):
            formatted.append(HumanMessage(content=message.content))
        elif isinstance(message, AIMessage):
            formatted.append(AIMessage(content=message.content))
        elif isinstance(message, BaseMessage) and isinstance(message.content, str):
            formatted.append(message)

    chain = model | StrOutputParser()
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    token_callback = configurable.get("token_callback")

    print("\n======= Streaming Answer =======\n")

    # Stream tokens one by one for real-time UI updates via WebSocket
    final_answer = ""
    async for token in chain.astream(formatted):
        if not token:
            continue
        print(token, end="", flush=True)
        final_answer += token
        if token_callback:
            callback_result = token_callback(token)
            if inspect.isawaitable(callback_result):
                await callback_result

    print("\n\n======= Done =======\n")

    # Cache the answer in Valkey (1 hour TTL)
    if valkey and final_answer:
        try:
            cache_key = get_answer_cache_key(state.get("prompt", ""), memory_context, skill_context)
            cache_data = {
                "final_answer": final_answer,
                "intent": intent,
            }
            valkey.setex(cache_key, 3600, json.dumps(cache_data))
        except Exception as e:
            print(f"Valkey Cache Error (General): {e}")

    # Return new message; add_messages annotation handles appending to history
    return {
        "final_answer": final_answer,
        "messages": [AIMessage(content=final_answer)],
        "intent": intent,
        "diagram_svg": state.get("diagram_svg"),
        "pdf_filename": state.get("pdf_filename"),
    }

# ---------------- DIAGRAM NODE ----------------

async def generate_diagram_node(state: State):
    """
    Uses LLM to generate Mermaid.js flowchart code from the query/sub-queries.
    """
    sub_queries = state.get("sub_queries", [])
    query_context = ", ".join(sub_queries) if sub_queries else state.get("prompt")

    system_prompt = (
        "You are a Mermaid.js expert. Generate a 'graph TD' flowchart.\n"
        "STRICT SYNTAX RULES:\n"
        "1. Use ONLY alphanumeric characters for node IDs (e.g., S1, Node1).\n"
        "2. ALL labels must be in double quotes: ID[\"Label Text\"].\n"
        "3. Do NOT use subgraphs, custom classes, or styling (%% or classDef).\n"
        "4. Do NOT use special hyphens (‑), ampersands (&), or slashes (/) inside labels.\n"
        "5. Return ONLY the raw code starting with 'graph TD'. No markdown backticks."
    )

    response = await model.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Create a logic diagram for: {query_context}")
    ])

    mermaid_code = sanitize_mermaid(response.content)  # type: ignore

    print(f"--- DEBUG: Generated Mermaid ---\n{mermaid_code}\n-------------------")

    return {"diagram_code": mermaid_code}

# ---------------- RAG / SEARCH NODES ----------------
# These nodes form the retrieval-augmented generation pipeline

async def search_node(state: State):
    """Runs web search using DuckDuckGo for each sub-query."""
    # Dynamically read the breadth decided by the Planner
    breadth = state.get("max_search_results", 2)
    sub_queries = state.get("sub_queries", [])

    # Fallback: if planner didn't generate sub-queries, use original prompt
    if not sub_queries:
        sub_queries = [state["prompt"]]

    results = await orchestrated_search_async(sub_queries, max_results=breadth)
    return {"search_results": results}

async def clean_node(state: State):
    """Scrapes and cleans the HTML content from search result URLs."""
    urls = []
    for item in state["search_results"]:  # type: ignore
        urls.extend(item["urls"])
    cleaned = await clean_multiple_urls(urls)
    return {"clean_text": cleaned}

def retrieve_node(state: State):
    """Retrieves relevant chunks from MongoDB vector store (web-sourced docs)."""
    res = retrieve_chunks_node(state)
    return {**res, "rag_done": True}


def document_retrieve_node(state: State):
    """Retrieves chunks from user-uploaded documents only."""
    res = retrieve_uploaded_chunks_node(state)
    return {**res, "rag_done": True}


def hybrid_retrieve_node(state: State):
    """Combines web-sourced and uploaded document retrieval, deduplicates results."""
    web_res = retrieve_chunks_node(state)
    doc_res = retrieve_uploaded_chunks_node(state)

    # Merge and deduplicate chunks from both sources
    merged_chunks = []
    seen_chunks = set()
    for chunk in (web_res.get("retrieved_chunks", []) + doc_res.get("retrieved_chunks", [])):
        if not isinstance(chunk, str):
            continue
        key = chunk.strip()
        if not key or key in seen_chunks:
            continue
        seen_chunks.add(key)
        merged_chunks.append(chunk)

    merged_docs = []
    seen_docs = set()
    for doc in (web_res.get("retrieved_documents", []) + doc_res.get("retrieved_documents", [])):
        if not isinstance(doc, dict):
            continue
        key = (doc.get("title", ""), doc.get("url", ""))
        if key in seen_docs:
            continue
        seen_docs.add(key)
        merged_docs.append(doc)

    return {
        "retrieved_chunks": merged_chunks,
        "retrieved_documents": merged_docs,
        "rag_done": True,
    }

async def diagram_wrapper(state: State):
    """Generates mermaid code via LLM, then renders it to a PNG image."""
    res = await generate_diagram_node(state)  # type: ignore
    mermaid_text = res["diagram_code"]

    image_path = f"static/diagram/{uuid.uuid4().hex[:8]}.png"
    await generate_diagram(mermaid_text, image_path)

    return {
        "diagram_code": mermaid_text,
        "diagram_svg": image_path,
        "diagram_done": True,
    }

# ---------------- JOIN NODE ----------------
# Synchronization point: waits for parallel branches (RAG + diagram) to finish

def join_node(state: State):
    """No-op node that acts as a sync barrier for parallel branches."""
    return {}

def join_router(state: State):
    """Decides if all parallel branches are done, or if we need to wait."""
    intent      = state.get("intent", "general")
    rag_done    = state.get("rag_done", False)
    diagram_done = state.get("diagram_done", False)
    research_enabled = bool(state.get("research_enabled", False))

    if intent == "research_with_diagram":
        if not research_enabled:
            return "answer_node" if diagram_done else "join_node"
        return "answer_node" if (rag_done and diagram_done) else "join_node"

    # PDF intent needs RAG to be done before generating the answer
    if intent in {"research", "how_to", "recommendation", "pdf",
                  "question_answer", "calculation", "transformation"}:
        return "answer_node" if rag_done else "join_node"

    if intent == "diagram":
        return "answer_node" if diagram_done else "join_node"

    return "answer_node"

# ---------------- ROUTERS ----------------
# These functions decide which path the graph takes based on state

def route_after_planner(state: State):
    """
    Main routing decision after the planner determines intent.
    Routes to: coding, diagram, search, document retrieval, or general chat.
    """
    intent = state.get("intent", "general")
    research_enabled = state.get("research_enabled", True)
    route_source = state.get("route_source", "web")
    uploaded_files_available = bool(
        state.get("uploaded_files_available")
        or state.get("uploaded_files")
    )

    # Coding bypasses everything - goes straight to E2B sandbox
    if intent == "coding":
        return "coding_node"

    # Diagram routes
    if intent == "research_with_diagram":
        if not research_enabled:
            return "diagram_wrapper"
        if route_source == "document":
            return ["embed_queries_node", "diagram_wrapper"]
        return ["search_node", "diagram_wrapper"]

    if intent == "diagram":
        return "diagram_wrapper"

    # If user uploaded files and router selected document/hybrid retrieval
    if uploaded_files_available and route_source == "document":
        return "embed_queries_node"

    if uploaded_files_available and route_source == "hybrid":
        return "search_node" if research_enabled else "embed_queries_node"

    # Simple greetings / non-research queries go to general chat
    if intent == "general" or not research_enabled:
        return "general_answer_node"

    if route_source == "document":
        return "embed_queries_node"

    # Default: web search pipeline
    return "search_node"

def route_from_search(state: State):
    """After search, always proceed to clean the scraped text."""
    return ["clean_node"]


def route_after_embeddings(state: State):
    """After embedding queries, route to the appropriate retrieval node."""
    route_source = state.get("route_source", "web")
    if route_source == "document":
        return "document_retrieve_node"
    if route_source == "hybrid":
        return "hybrid_retrieve_node"
    return "retrieve_node"


def route_after_answer(state: State):
    """After generating the answer, check if we need to create a PDF."""
    if state.get("intent") == "pdf":
        return "pdf_node"
    return END

# ================== BUILD THE GRAPH ==================
# This is where we wire all nodes and edges together

builder = StateGraph(State)

# ── Register all nodes ──
builder.add_node("check_uploaded_files_node", check_uploaded_files_node)
builder.add_node("cache_check_node",         cache_check_node)
builder.add_node("document_intent_node",     document_intent_node)
builder.add_node("planner_node",             planner_node)
builder.add_node("general_answer_node",      general_answer_node)

builder.add_node("search_node",              search_node)
builder.add_node("clean_node",               clean_node)
builder.add_node("chunk_text_node",          chunk_text_node)
builder.add_node("embed_and_store_node",     embed_and_store_node)
builder.add_node("embed_queries_node",       embed_queries_node)
builder.add_node("retrieve_node",            retrieve_node)
builder.add_node("document_retrieve_node",   document_retrieve_node)
builder.add_node("hybrid_retrieve_node",     hybrid_retrieve_node)

builder.add_node("diagram_wrapper",          diagram_wrapper)
builder.add_node("join_node",                join_node)
builder.add_node("answer_node",              answer_node)
builder.add_node("coding_node",              coding_node)
builder.add_node("pdf_node",                 generate_pdf_node)

# ── Define the flow (edges) ──

def route_after_cache(state: State):
    """If cache hit, skip everything and end. Otherwise continue pipeline."""
    if state.get("cache_hit"):
        return END
    return "document_intent_node"

# Entry point: first check if user has uploaded files in this session
builder.add_edge(START, "check_uploaded_files_node")
builder.add_edge("check_uploaded_files_node", "cache_check_node")

# Cache check: if we have a cached answer, return immediately
builder.add_conditional_edges(
    "cache_check_node",
    route_after_cache,
    {
        END: END,
        "document_intent_node": "document_intent_node"
    }
)

# Document intent determines if query needs web, document, or hybrid retrieval
builder.add_edge("document_intent_node", "planner_node")

# Planner routes to the appropriate execution path
builder.add_conditional_edges(
    "planner_node",
    route_after_planner,
    {
        "coding_node": "coding_node",
        "general_answer_node": "general_answer_node",
        "diagram_wrapper": "diagram_wrapper",
        "embed_queries_node": "embed_queries_node",
        "search_node": "search_node",
    }
)

builder.add_conditional_edges(
    "search_node",
    route_from_search,
    {
        "clean_node": "clean_node",
        "diagram_wrapper": "diagram_wrapper"
    }
)

# RAG pipeline: search -> clean -> chunk -> embed -> retrieve
builder.add_edge("clean_node",           "chunk_text_node")
builder.add_edge("chunk_text_node",      "embed_and_store_node")
builder.add_edge("embed_and_store_node", "embed_queries_node")

# After embedding queries, pick the right retrieval strategy
builder.add_conditional_edges(
    "embed_queries_node",
    route_after_embeddings,
    {
        "retrieve_node": "retrieve_node",
        "document_retrieve_node": "document_retrieve_node",
        "hybrid_retrieve_node": "hybrid_retrieve_node",
    },
)

# All retrieval nodes converge at the join node
builder.add_edge("retrieve_node",           "join_node")
builder.add_edge("document_retrieve_node",  "join_node")
builder.add_edge("hybrid_retrieve_node",    "join_node")

# Diagram also converges at join
builder.add_edge("diagram_wrapper", "join_node")

# Join waits for all parallel branches, then proceeds to answer
builder.add_conditional_edges(
    "join_node",
    join_router,
    {
        "join_node":   "join_node",
        "answer_node": "answer_node",
    }
)

# After answer: generate PDF if needed, otherwise end
builder.add_conditional_edges(
    "answer_node",
    route_after_answer,
    {
        "pdf_node": "pdf_node",
        END:        END,
    }
)

# Terminal edges - these nodes go straight to END
builder.add_edge("general_answer_node", END)
builder.add_edge("coding_node",         END)
builder.add_edge("pdf_node",            END)

# ---------------- COMPILE ----------------
# MemorySaver keeps conversation state across turns (in-memory checkpointing)

from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# Compile the graph into an executable runnable
graph = builder.compile(checkpointer=checkpointer)
