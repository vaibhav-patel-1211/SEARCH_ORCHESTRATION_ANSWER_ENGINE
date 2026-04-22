import os
import sys
import asyncio
import warnings

# Fix for Playwright/Subprocess on Windows: NotImplementedError
# This must be set before any event loop is created or used.
if sys.platform == "win32":
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_huggingface import HuggingFaceEmbeddings
from flashrank import Ranker
import redis
import json

# Suppress the reasoning parsing warning from the NVIDIA library
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_nvidia_ai_endpoints")

load_dotenv()


model = ChatNVIDIA(
  # openai/gpt-oss-120b
  model = 'openai/gpt-oss-120b',
  api_key=os.getenv("OPEN_AI_KEY"),
  max_tokens=8192,
)

coding_model = ChatNVIDIA(
  model = 'minimaxai/minimax-m2.5',
  api_key=os.getenv("OPEN_AI_KEY"),
  max_tokens=4000,
)

embedding_model = HuggingFaceEmbeddings(
  model_name =  'sentence-transformers/all-MiniLM-L6-v2',
)

# Reranker for production-ready RAG
reranker = Ranker()

# Valkey / Redis client (Protocol Compatible)
# Set host and port via environment variables or use defaults
VALKEY_HOST = os.getenv("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", 6379))

try:
    valkey = redis.Redis(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        decode_responses=True,
        socket_timeout=2
    )
    # Fast health check
    valkey.ping()
    print(f"✅ Valkey Connected (Host: {VALKEY_HOST}:{VALKEY_PORT})")
except Exception:
    print(f"⚠️ Valkey not available at {VALKEY_HOST}:{VALKEY_PORT}. Caching disabled.")
    valkey = None




