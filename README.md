# Horizon: Search Orchestration Answer Agent 🚀

**Horizon** is a sophisticated, agentic AI assistant built with a **Neo-Brutalist** aesthetic. It leverages **LangGraph** for multi-step orchestration, combining advanced RAG, secure code execution, and real-time visualization to provide comprehensive, verified answers.


---

## 🌟 Key Features

### 🧠 Agentic Orchestration (LangGraph)
Unlike standard chatbots, Horizon uses a **state-machine-driven graph** to plan and execute tasks.
- **Dynamic Planning:** A dedicated planner node analyzes user intent to determine search breadth and retrieval depth.
- **Conditional Routing:** Automatically routes queries to the most relevant tools (Web Search, Document Retrieval, Coding Sandbox, or Diagram Generator).

### 🔍 Advanced RAG & Multi-Document QA
- **Ingestion Pipeline:** Supports PDF, DOCX, and TXT files with intelligent chunking and metadata extraction.
- **Vector Search:** Powered by **MongoDB Atlas Vector Search** for high-performance semantic retrieval.
- **Hybrid Retrieval:** Combines web search (DuckDuckGo) with private document context for grounded answers.

### 💻 Secure Code Execution (E2B)
- **Verified Coding:** Generates and executes Python code within a secure **E2B Sandbox**.
- **Self-Healing Code:** If execution fails, an LLM-based "fixer" node automatically debugs and corrects the code before returning the result.

### 📊 Visual Insights & Reporting
- **Diagram Generation:** Automatically generates **Mermaid.js** flowcharts and diagrams for logical queries.
- **PDF Reports:** Exports comprehensive research findings into professionally formatted PDF documents.

### ⚡ Real-time Performance
- **WebSocket Streaming:** Tokens and tool-call events are streamed in real-time for a low-latency user experience.
- **Intelligent Caching:** Uses **Redis/Valkey** to cache frequent queries and intermediate graph states.

---

## 🛠️ Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Orchestration:** LangChain & LangGraph
- **LLMs:** NVIDIA AI Endpoints, DeepSeek (configurable)
- **Database:** MongoDB Atlas (Vector Store & Session Data)
- **Sandbox:** E2B Code Interpreter
- **Auth:** JWT (python-jose) & Bcrypt

### Frontend
- **Framework:** React 19 (Vite)
- **Styling:** Neo-Brutalist CSS (Bold borders, heavy shadows, high contrast)
- **Icons:** Lucide React
- **Streaming:** Native WebSockets

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js & npm
- MongoDB Atlas Account (Vector Search enabled)
- API Keys: NVIDIA/OpenAI/DeepSeek, E2B_API_KEY, MONGODB_URI

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
1. **Input:** User query received via WebSocket or REST.
2. **Planner:** Determines intent (Search vs. RAG vs. Code vs. General).
3. **Execution Nodes:**
   - `search_node`: Fetches web data.
   - `retrieve_chunks`: Queries MongoDB Vector store.
   - `coding_node`: Runs code in E2B.
   - `diagram_node`: Generates Mermaid syntax.
4. **Synthesizer:** Aggregates all data into a final, grounded response.
5. **Output:** Streamed back to the React UI.

---

## 🤝 Contributing
Contributions are welcome! Please open an issue or submit a pull request for any improvements.

