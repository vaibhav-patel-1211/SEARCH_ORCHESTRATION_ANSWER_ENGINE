# Horizon — Search Orchestration Answer Engine
### College Project Presentation Document

---

## 1. What Is This Project?

**Horizon** is an AI-powered answer engine that does not just chat — it *thinks, plans, searches, retrieves, codes, and verifies* before giving you an answer.

Most AI chatbots (ChatGPT, Claude) work like this:
> User types → LLM replies.

Horizon works like this:
> User types → **Planner decides a strategy** → Multiple specialized agents run in parallel → Results are aggregated → Verified answer is streamed back.

It is built on top of **LangGraph**, which lets us define the AI as a **state machine graph** — a flowchart of intelligent nodes — instead of a single model call. Every query goes through a different path depending on what kind of question it is.

---

## 2. The Core Idea — Why We Built This

Standard LLMs have three fundamental problems:

| Problem | How Horizon Solves It |
|---|---|
| Knowledge cut-off (stale data) | Real-time DuckDuckGo web search |
| Hallucination (making things up) | RAG: answers grounded in retrieved sources |
| Can't run or verify code | E2B Sandbox: code is actually executed and self-healed |

The goal is a **single interface** that replaces: a search engine + a document reader + a coding IDE + a diagram tool + a research assistant.

---

## 3. Full Feature List

### 🧠 Agentic Orchestration (LangGraph)
- The entire backend is a **directed acyclic graph (DAG)** of AI nodes built with LangGraph
- A dedicated **Planner node** (`graph/steps/planner.py`) reads every user query and decides:
  - What is the *intent*? (research, coding, general, diagram, PDF, Q&A, calculation...)
  - How many search results to fetch? (`max_search_results`)
  - How deep to retrieve? (`retrieval_limit`)
  - Should web search be enabled?
  - What sub-queries to generate?
- This planning happens via **structured output** from the LLM (Pydantic schema `ExecutionPlan`)
- A fast-path heuristic in the planner instantly detects coding queries without an LLM call

### 🔍 Multi-Step Web Research (RAG Pipeline)
- **DuckDuckGo Search** (`graph/steps/search.py`) — free, no API key, concurrent async searches
- **Web scraping + cleaning** (`graph/steps/clean_text.py`) — fetches and cleans raw HTML from URLs
- **Text chunking** (`graph/steps/chunking.py`) — splits content into overlapping chunks (1200 chars, 200 overlap)
- **Vector embedding** (`graph/steps/embed_queries.py`, `store_embeddings.py`) — uses HuggingFace `all-MiniLM-L6-v2` model
- **MongoDB Atlas Vector Search** — stores and retrieves semantically similar chunks
- **FlashRank reranker** (`config.py`) — reranks retrieved chunks by relevance before generating the answer
- All of this runs in a pipeline: Search → Clean → Chunk → Embed → Store → Retrieve → Synthesize

### 📄 Document Intelligence (Uploaded Files)
- Upload PDF, DOCX, or TXT files (`app/services/document_ingestion.py`)
- Files are parsed, chunked, embedded and stored in MongoDB Atlas with session metadata
- A **Document Intent Router** (`graph/steps/document_intent.py`) detects whether the user is asking about their uploaded file or the web
- Three retrieval modes: `document` (only file), `web` (only internet), `hybrid` (merge both)
- Hybrid retrieval deduplicates chunks from both sources before answering

### 💻 Secure Code Execution with Self-Healing
- Detected via a two-layer system: fast regex heuristic (no LLM needed) + LLM fallback
- Python code is generated, then **actually executed** inside an **E2B cloud sandbox** (`graph/steps/coding.py`)
- If execution fails, an LLM "fixer" node automatically reads the error, rewrites the code, and retries — up to 3 times
- Uses a separate `coding_model` (NVIDIA endpoint) for higher-quality code generation
- Returns both the code and the execution output

### 📊 Diagram Generation
- Detects diagram/flowchart requests by keyword matching
- LLM generates valid **Mermaid.js** syntax with strict rules to avoid syntax errors
- A sanitizer cleans the output (removes illegal characters, enforces `graph TD` format)
- Diagram is rendered server-side and the image is served as a static file

### 📋 PDF Report Export
- For research-heavy queries (intent = `pdf`), after generating the answer, a separate node (`graph/steps/generate_pdf.py`) uses E2B sandbox to run a Python PDF-generation script (ReportLab)
- The PDF is saved and a download link is returned to the frontend

### ⚡ Intelligent Caching (Valkey/Redis)
- **Two levels of caching:**
  1. **Search cache** — DuckDuckGo results are cached for 1 hour per query hash
  2. **Answer cache** — final answers are cached per prompt hash
- Cache is skipped automatically when: diagram prompts are detected, uploaded files exist, user memory context is present, or a skill is active
- Uses **Valkey** (Redis-compatible) as the cache store

### 🧠 Persistent User Memory
- After every conversation, an LLM extracts key facts about the user (name, preferences, goals) and stores them in MongoDB (`app/services/user_memory.py`)
- These memories are injected as context in future conversations for personalization
- Users can view, add, and delete memories from the Customize panel
- Memory extraction can be disabled by the user

### 🎯 Custom Skills System
- Users define **Skills** — named instruction sets with triggers and a custom system prompt (`app/services/skills.py`)
- Defined in a simple YAML-like frontmatter format:
  ```
  ---
  name: exam
  triggers: [explain, overview, what is]
  prompt: Explain the topic with key milestones...
  ---
  ```
- The skill can be **manually selected** from the chat input (Zap button) or auto-matched by triggers
- When a skill is used, it is shown as a badge on the assistant message
- Multiple skills supported; each can be toggled on/off

### 💾 Saved Prompts & Prompt Commands
- Users can save frequently used prompts with names
- Use them in chat via `/command:` syntax (e.g., `/RESEARCH:`)
- Autocomplete dropdown appears as you type `/`

### ✨ Prompt Optimizer
- A dedicated view where users can paste any rough prompt
- An LLM (prompted as a "senior prompt engineer") rewrites it into a high-quality, detailed prompt
- One-click insert into the chat input

### 🔐 Authentication (JWT)
- Full signup/login flow with JWT tokens (`app/api/v1/auth.py`)
- Bcrypt password hashing
- Tokens stored in `localStorage`, validated on every API/WebSocket call
- Expired sessions are automatically detected and the user is logged out

### 📡 Real-time WebSocket Streaming
- Every chat message streams back token by token via WebSocket (`app/api/v1/ws_chat.py`)
- Events are typed: `token`, `tool_call`, `retrieval`, `final_answer`, `error`
- The frontend renders a **thinking panel** in real-time showing each step (query understanding, web search, retrieval, skill match)
- Research progress bar with 5 stages rendered live

### 🖥️ Live Code Preview Canvas
- When an assistant response contains HTML/CSS/JS/JSX/React code, a **Preview (Monitor) button** appears
- Opens a full canvas panel with an `<iframe srcdoc>` rendering the output live
- React/JSX blocks automatically load Babel + React from CDN for in-browser rendering
- Device switcher: Desktop / Tablet (768px) / Mobile (390px) with smooth transitions
- macOS-style traffic lights, refresh button

### 🎨 Neo-Brutalist UI
- Bold black borders, heavy drop shadows, high-contrast colors
- Fully responsive sidebar with collapse/expand
- Chat history with rename/delete modals
- File upload with progress bar, preview panel with PDF iframe support

---

## 4. System Architecture — How Data Flows

```
User Query (WebSocket)
        │
        ▼
┌─────────────────────┐
│  check_uploaded_    │  ← Are files attached to this session?
│  files_node         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  cache_check_node   │  ← Is this a cached query? If yes → END
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  document_intent_   │  ← Should we use uploaded docs or web?
│  node               │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  planner_node       │  ← LLM decides: intent, breadth, depth, sub-queries
└────────┬────────────┘
         │
    ┌────┴───────────────────────────┐
    │                                │
    ▼                                ▼
[coding]              [research / document / diagram / general]
    │                                │
    ▼                                ▼
coding_node          ┌──────────────────────────────────┐
(E2B sandbox)        │   search_node (DuckDuckGo)        │
                     │   clean_node (web scraping)       │
                     │   chunk_text_node                 │
                     │   embed_and_store_node (MongoDB)  │
                     │   embed_queries_node              │
                     │   retrieve_node (vector search)   │
                     └─────────────┬────────────────────┘
                                   │
                                   ▼
                            join_node (sync parallel branches)
                                   │
                                   ▼
                            answer_node (LLM synthesis with context)
                                   │
                              [if pdf intent]
                                   ▼
                            pdf_node (E2B → ReportLab)
                                   │
                                   ▼
                         Final Answer streamed to frontend
```

---

## 5. How Each Intent Works — Prompt Walkthroughs

### 5a. Normal/General Chat
**Prompt:** `"What is your name?"` or `"Tell me a joke"`

- Planner detects intent = `general`, research_enabled = false
- Routes directly to `general_answer_node` — no search, no retrieval
- A personalized system prompt is built using the user's stored memory
- LLM streams the response token by token
- **Fastest path** — typically < 2 seconds

---

### 5b. Research Query
**Prompt:** `"Explain how transformer architecture works"` (with web search toggle ON)

- Planner detects intent = `research`, generates 4-6 sub-queries
- `search_node` fires all sub-queries concurrently against DuckDuckGo
- `clean_node` scrapes and cleans the raw HTML content from each URL
- `chunk_text_node` splits all text into 1200-character overlapping chunks
- `embed_and_store_node` embeds chunks using MiniLM and stores in MongoDB Atlas
- `embed_queries_node` embeds the original question
- `retrieve_node` does vector similarity search, retrieves top-K chunks
- FlashRank reranker reorders chunks by relevance
- `answer_node` gets the ranked chunks + source URLs as context, generates a grounded answer
- Frontend shows the 5-stage **Research Progress Bar** live

---

### 5c. Coding Query
**Prompt:** `"Write a Python script to scrape prices from Amazon"` or `"Fix this error: IndexError on line 12"`

- Planner fast-path detects coding keywords + tech keywords instantly (no LLM call)
- Routes directly to `coding_node`
- `coding_model` (NVIDIA endpoint) generates the code
- Code is extracted from the LLM markdown response
- Code is sent to an **E2B cloud sandbox** (isolated container) and executed
- If execution fails → LLM reads the error traceback → rewrites the code → retries (up to 3x)
- Returns code + stdout/stderr output
- The **Live Preview** button appears if it's HTML/CSS/JS — user can see the rendered output instantly

---

### 5d. Attached PDF / Document Query
**Prompt:** `"Summarize the key findings in this research paper"` (with PDF uploaded)

- `check_uploaded_files_node` confirms files are in the session → sets `uploaded_files_available = True`
- `document_intent_node` sees hints like "this document", "summarize" → routes to `document` mode
- `embed_queries_node` embeds the question
- `retrieve_uploaded_chunks_node` searches MongoDB Atlas for chunks from *this specific file only* (filtered by `file_id`)
- Answer is generated grounded in the document content
- The file name appears as a **Context badge** on the user message

---

### 5e. Hybrid (Web + Uploaded Document)
**Prompt:** `"Compare what this PDF says about neural networks vs latest research"` (with PDF uploaded)

- `document_intent_node` detects both document hints AND web research need → `hybrid` mode
- `search_node` AND `embed_queries_node` run in parallel
- `hybrid_retrieve_node` merges and deduplicates chunks from both sources
- Final answer synthesizes both the uploaded document and current web sources

---

### 5f. Diagram Query
**Prompt:** `"Draw a flowchart of the login authentication process"`

- Planner detects intent = `diagram`
- `generate_diagram_node` asks LLM to generate strict Mermaid.js `graph TD` syntax
- Sanitizer cleans the output (removes illegal chars, subgraphs, styling)
- `generate_diagram` renders it to a PNG image server-side
- Image URL is returned and displayed inline in the chat

---

### 5g. PDF Report Generation
**Prompt:** `"Generate a research report on quantum computing"` (with web search + intent resolved to `pdf`)

- Full research pipeline runs (search → clean → chunk → embed → retrieve → answer)
- After the answer is generated, `generate_pdf_node` runs
- Uses E2B sandbox to execute a Python script (ReportLab) that formats the answer as a styled PDF
- A **Download PDF Report** button appears in the chat

---

### 5h. With a Custom Skill
**Prompt:** `"Explain neural networks"` (user has a skill named "exam" with trigger "explain")

- `match_skills` finds the skill by trigger word OR user manually selects it via the ⚡ button
- Skill's custom prompt is prepended to the system context
- The answer follows the skill's instructions (e.g., "explain with definition, milestones, pros/cons...")
- A **Skill badge** appears on the assistant message showing which skill was used

---

## 6. How Is This Different from ChatGPT and Claude?

| Feature | ChatGPT | Claude | **Horizon** |
|---|---|---|---|
| Real-time web search | GPT-4o with browsing (paid) | Claude.ai with search (limited) | **Always available, free (DuckDuckGo)** |
| Document upload | Yes (GPT-4 paid) | Yes | **Yes, with hybrid web+doc retrieval** |
| Code execution | Code interpreter (paid) | No | **Yes, with self-healing (E2B sandbox)** |
| Answer grounding | Often hallucinates | Often hallucinates | **Sources shown, chunks retrieved** |
| Memory | Limited (ChatGPT memory) | No | **Persistent MongoDB memory, user-controlled** |
| Custom skills/personas | Custom GPTs (paid) | Styles (limited) | **Full YAML skill system, trigger-based** |
| Diagram generation | No | No | **Yes, Mermaid.js rendered to image** |
| PDF report export | No | No | **Yes, formatted PDF download** |
| Live code preview | No | No | **Yes, iframe canvas with device preview** |
| Prompt optimizer | No | No | **Built-in prompt engineer** |
| Saved prompt commands | No | No | **Yes, /command: autocomplete** |
| Open source / self-hostable | No | No | **Yes, full stack** |
| Transparent reasoning | Hidden | Hidden | **Thinking panel shows every step live** |
| Caching | No | No | **Two-level Valkey/Redis cache** |

The biggest difference: **Horizon is an orchestrator, not a chatbot.** It decides *how* to answer your question — which tools to use, in what order, with what depth — rather than just predicting the next word.

---

## 7. How We Built Each Feature

### Backend Architecture
- **FastAPI** serves the REST API and WebSocket endpoint
- All routes are organized under `app/api/v1/` — `auth.py`, `chat.py`, `ws_chat.py`, `upload.py`
- The WebSocket handler (`ws_chat.py`) manages concurrent requests with `asyncio.Task` and supports cancellation
- MongoDB (via Motor async driver) stores sessions, messages, files, memories, skills, and saved prompts

### LangGraph State Machine
- Defined in `graph/graph.py` as a `StateGraph` with a typed `State` dict
- Each node is a Python async function that reads from state and returns partial updates
- Conditional edges implement routing logic (e.g., `route_after_planner` returns different node names based on intent)
- Parallel branches (research + diagram) are synchronized via a `join_node` that waits for both to complete
- `MemorySaver` checkpointer enables session-level memory persistence across the graph

### RAG Pipeline
- We chose **HuggingFace sentence-transformers** (MiniLM-L6-v2) for embeddings — fast, free, runs locally
- MongoDB Atlas provides native vector search with cosine similarity
- We implemented **FlashRank** reranking on top of vector search for higher precision
- Chunk size (1200) and overlap (200) were tuned to balance context window and retrieval granularity

### Coding Node
- The two-layer detection (regex fast-path + LLM) avoids unnecessary LLM calls for obvious coding questions
- E2B provides a real cloud sandbox — much safer than running `exec()` locally
- The self-healing loop uses the error output as context for the fix prompt — this is a common "reflection" pattern in agentic AI

### Skills System
- The skill definition format uses YAML-like frontmatter (parsed in `app/services/skills.py`)
- `match_skills` does keyword-level trigger matching with word boundary awareness
- Skills are stored per-user in MongoDB and cached in the app state
- The manual selection sends `skill_id` over WebSocket, bypassing trigger matching entirely

### User Memory
- After each assistant response, an async background task runs an LLM extraction prompt
- The LLM returns structured `{key, value, confidence}` objects
- These are upserted (not appended) to MongoDB — same key updates, doesn't grow unboundedly
- Memory context is injected as a private section in the system prompt

### Frontend
- Built with **React 19 + Vite** — fast HMR for development, optimized bundle for production
- WebSocket connection is managed at the App level with `useRef` to avoid re-renders
- The thinking panel renders `thinkingSteps` array that is updated in real-time as `tool_call` events arrive
- The live preview uses `srcdoc` on an `<iframe>` with `sandbox="allow-scripts"` — safe, no network access

---

## 8. Tech Stack Summary

| Layer | Technology | Why |
|---|---|---|
| Backend framework | FastAPI (Python) | Async, fast, auto-docs |
| AI Orchestration | LangGraph + LangChain | Graph-based state machine |
| LLM Provider | NVIDIA AI Endpoints (GPT-OSS-120B) | High quality, OpenAI-compatible API |
| Embeddings | HuggingFace MiniLM-L6-v2 | Free, fast, good quality |
| Vector Database | MongoDB Atlas | Native vector search + document storage |
| Code Sandbox | E2B Cloud Interpreter | Secure, isolated Python execution |
| Caching | Valkey (Redis-compatible) | Search + answer cache |
| Authentication | JWT + Bcrypt | Standard, stateless |
| Frontend | React 19 + Vite | Fast, component-based |
| Styling | Neo-Brutalist CSS | Bold, high-contrast, distinctive |
| Icons | Lucide React | Clean, consistent icon set |
| Markdown | react-markdown + remark-gfm | Full GFM rendering |

---

## 9. Future Enhancements

### Near-Term (Next 3 Months)
1. **Multi-model routing** — Route coding to DeepSeek Coder, creative tasks to Claude, research to GPT-4, based on intent
2. **Voice input/output** — Web Speech API for voice queries + TTS for spoken answers
3. **Browser extension** — Summarize any webpage with one click, injecting it as context
4. **Table/spreadsheet extraction** — Parse Excel/CSV files, allow natural language queries on tabular data

### Medium-Term (3–6 Months)
5. **Multi-agent collaboration** — Spawn sub-agents that specialize in different domains and report back to a coordinator
6. **Autonomous research mode** — Given a topic, automatically plan, search, read, iterate, and produce a full report without user intervention
7. **Plugin/tool ecosystem** — Allow users to add custom tools (e.g., call a REST API, query a database) via a tool registry
8. **Citation tracking** — Track exactly which chunk from which source was used in which sentence of the answer

### Long-Term (6+ Months)
9. **Fine-tuned planner model** — Train a small model specifically for intent classification and query decomposition, replacing the LLM call in the planner for near-zero latency routing
10. **Multi-modal input** — Image understanding (charts, diagrams, screenshots) using vision models
11. **Collaborative sessions** — Multiple users in the same research session with real-time sync
12. **Local LLM support** — Ollama integration for fully offline, private usage
13. **Evaluation framework** — Automated testing of answer quality, source attribution accuracy, and code correctness

---

## 10. Project Statistics

| Metric | Value |
|---|---|
| Backend Python files | ~25 files |
| Frontend React components | ~12 components |
| LangGraph nodes | 15 nodes |
| Intent types supported | 9 (general, research, coding, diagram, research_with_diagram, pdf, how_to, recommendation, question_answer) |
| API endpoints | ~20 REST + 1 WebSocket |
| Lines of code (approx.) | ~5,000+ |
| Database collections | 6 (sessions, files, memories, skills, prompts, memory_settings) |

---

## 11. One-Line Pitch

> **"Horizon is not a chatbot — it is an AI agent that thinks before it speaks, searches before it answers, runs code before it claims it works, and learns who you are to serve you better every time."**

---

*Built with LangGraph · FastAPI · MongoDB Atlas · E2B · React 19 · NVIDIA AI Endpoints*
