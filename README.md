# Horizon: Search Orchestration Answer Agent 🚀

**Horizon** is a sophisticated, agentic AI assistant built with a **Neo-Brutalist** aesthetic. It leverages **LangGraph** for multi-step orchestration, combining advanced RAG, secure code execution, and real-time visualization to provide comprehensive, verified answers.


---

## 🌟 Key Features

### 🧠 Agentic Orchestration (LangGraph)
Unlike standard chatbots, Horizon uses a **state-machine-driven graph** to plan and execute tasks.
- **Dynamic Planning:** A dedicated planner node analyzes user intent to determine search breadth and retrieval depth.
- **Conditional Routing:** Automatically routes queries to the most relevant tools (Web Search, Document Retrieval, Coding Sandbox, or Diagram Generator).
- **Thinking Steps:** Real-time visibility into the agent's reasoning process (query understanding, search planning, source retrieval).

### 🔍 Advanced RAG & Multi-Document QA
- **Ingestion Pipeline:** Supports PDF, DOCX, and TXT files with intelligent chunking and metadata extraction.
- **Vector Search:** Powered by **MongoDB Atlas Vector Search** for high-performance semantic retrieval.
- **Hybrid Retrieval:** Combines web search (DuckDuckGo) with private document context for grounded answers.

### 💾 Long-term Memory & Personalization
- **User Memory:** Automatically extracts and stores durable facts about the user (preferences, technical stack, architectural decisions) to personalize future interactions.
- **Custom Skills:** User-definable "skills" that act as specialized system prompts, triggered automatically by keywords or selected manually for specific tasks.

### 💻 Secure Code Execution & Live Preview
- **Verified Coding:** Generates and executes Python code within a secure **E2B Sandbox**.
- **Live Preview:** Real-time rendering of HTML, CSS, JS, and React code blocks directly within the chat interface, supporting desktop, tablet, and mobile views.

### 📊 Visual Insights & Reporting
- **Diagram Generation:** Automatically generates **Mermaid.js** flowcharts and logic diagrams, rendered as high-quality PNGs.
- **PDF Reports:** Exports comprehensive research findings and chat responses into professionally formatted PDF documents.

### ⚡ Real-time Performance
- **WebSocket Streaming:** Tokens and tool-call events are streamed in real-time for a low-latency user experience.
- **Intelligent Caching:** Uses **Redis/Valkey** to cache frequent queries and intermediate graph states.

---

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Orchestration:** LangChain & LangGraph
- **LLMs:** NVIDIA AI Endpoints, DeepSeek, OpenAI (configurable)
- **Database:** MongoDB Atlas (Vector Store & Session Data)
- **Caching:** Redis / Valkey
- **Sandbox:** E2B Code Interpreter & Playwright (for diagram rendering)

### Frontend
- **Framework:** React 19 (Vite)
- **Styling:** Neo-Brutalist CSS (Bold borders, heavy shadows, high contrast)
- **Live Rendering:** Built-in code sandbox for HTML/JS/React previews
- **Streaming:** Native WebSockets

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js & npm
- MongoDB Atlas Account (Vector Search enabled)
- API Keys: NVIDIA/OpenAI/DeepSeek, E2B_API_KEY, MONGO_URI

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/search-orchestration-agent.git
   cd search-orchestration-agent
   ```

2. **Backend Setup**
   ```bash
   pip install -r requirements.txt
   cp .env.example .env  # Configure your keys
   uvicorn app.api.main:app --reload
   ```

3. **Frontend Setup**
   ```bash
   cd Horizon
   npm install
   npm run dev
   ```

---

## 🏗️ System Architecture

Horizon follows a modular graph-based architecture:
1. **Input:** User query received via WebSocket with session context (Memory + Skills).
2. **Pre-processing:** Cache check (Valkey) and session-file detection.
3. **Planner:** Determines intent (Search vs. RAG vs. Code vs. Diagram) and generates sub-queries.
4. **Execution Nodes:**
   - `search_node`: Fetches web data via DuckDuckGo.
   - `retrieve_node`: Queries MongoDB Vector store for web/document context.
   - `coding_node`: Runs Python code in E2B sandbox.
   - `diagram_node`: Generates Mermaid syntax and renders to PNG via Playwright.
5. **Post-processing:** Answer synthesis, PDF generation, and background memory extraction.
6. **Output:** Streamed tokens and "thinking" events pushed to the React UI via WebSockets.

---

## 🤝 Contributing
Contributions are welcome! Please open an issue or submit a pull request for any improvements.

