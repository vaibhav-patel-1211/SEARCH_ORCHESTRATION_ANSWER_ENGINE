"""
config.py - Central configuration for the Horizon project.
Loads environment variables, initializes LLM models, embedding model,
reranker, and the Valkey (Redis-compatible) cache connection.
"""

import os
import sys
import asyncio
import warnings

# Fix for Playwright/Subprocess on Windows: NotImplementedError
# Windows needs ProactorEventLoop for subprocess support in asyncio.
if sys.platform == "win32":
    try:
        from asyncio import WindowsProactorEventLoopPolicy, set_event_loop_policy
        set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception as e:
        print(f"⚠️ Could not set ProactorEventLoopPolicy: {e}")

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_huggingface import HuggingFaceEmbeddings
from flashrank import Ranker
import redis
import json

# Suppress the reasoning parsing warning from the NVIDIA library
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_nvidia_ai_endpoints")

# Load .env file so we can access API keys and config values
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_KEY")

# Primary LLM used for planning, answering, and general tasks
model = ChatNVIDIA(
  model = 'openai/gpt-oss-120b',
  api_key=OPENAI_API_KEY,
  max_tokens=8192,
)

# Separate model instance for code generation (same model, but kept separate
# so we can swap it independently if needed)
coding_model = ChatNVIDIA(
  model = 'openai/gpt-oss-120b',
  api_key=OPENAI_API_KEY,
  max_tokens=8192,
)

# Embedding model for converting text chunks into vectors
# Used in both ingestion (storing) and retrieval (querying) pipelines
embedding_model = HuggingFaceEmbeddings(
  model_name =  'sentence-transformers/all-MiniLM-L6-v2',
)

# FlashRank reranker - reorders retrieved chunks by relevance to the query
# This improves RAG accuracy by pushing the most relevant chunks to the top
reranker = Ranker()

# Valkey / Redis client (Protocol Compatible)
# Used for caching search results and final answers to reduce latency
VALKEY_HOST = os.getenv("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", 6379))

try:
    valkey = redis.Redis(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        decode_responses=True,
        socket_timeout=2
    )
    # Quick ping to verify connection is alive
    valkey.ping()
    print(f"✅ Valkey Connected (Host: {VALKEY_HOST}:{VALKEY_PORT})")
except Exception:
    # If Valkey isn't running, we just disable caching gracefully
    print(f"⚠️ Valkey not available at {VALKEY_HOST}:{VALKEY_PORT}. Caching disabled.")
    valkey = None
