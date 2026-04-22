import hashlib
import re
from config import valkey
from langchain_core.messages import AIMessage

def get_answer_cache_key(prompt):
    clean_p = prompt.strip().lower()
    return f"answer_cache:{hashlib.md5(clean_p.encode()).hexdigest()}"


_DIAGRAM_PROMPT_RE = re.compile(
    r"\b(diagram|flowchart|flow chart|architecture diagram|sequence diagram|mermaid|block diagram)\b",
    re.IGNORECASE,
)


def _looks_like_diagram_prompt(prompt: str) -> bool:
    return bool(_DIAGRAM_PROMPT_RE.search(prompt or ""))

def cache_check_node(state):
    user_prompt = state.get("prompt", "")
    if _looks_like_diagram_prompt(user_prompt):
        print("DEBUG: Skipping cache for diagram-oriented prompt.")
        return {"cache_hit": False}
    if state.get("uploaded_files_available"):
        print("DEBUG: Skipping cache because uploaded files are available in session.")
        return {"cache_hit": False}
    if state.get("memory_context"):
        print("DEBUG: Skipping cache because user memory context is available.")
        return {"cache_hit": False}

    print(f"DEBUG: cache_check_node received prompt: '{user_prompt}'")
    
    if valkey:
        cache_key = get_answer_cache_key(user_prompt)
        print(f"DEBUG: Checking cache key: {cache_key}")
        try:
            cached_answer = valkey.get(cache_key)
            if cached_answer:
                print(f"🚀 Valkey Hit: Instant response for '{user_prompt[:30]}...'")
                # We MUST return messages so the API sees the answer
                return {
                    "final_answer": cached_answer, 
                    "messages": [AIMessage(content=cached_answer)],
                    "cache_hit": True
                }
            else:
                print(f"DEBUG: Cache miss for '{user_prompt[:30]}...'")
        except Exception as e:
            print(f"Valkey Cache Read Error: {e}")
            
    return {"cache_hit": False}
