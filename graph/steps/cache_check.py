"""
cache_check.py - First real logic node in the pipeline.
Checks if we already have a cached answer for this exact query in Valkey.
If yes, returns it immediately (skips the entire pipeline).
If no, continues to the next node.

Skips cache for:
  - Sessions with uploaded files (context-dependent)
"""

import hashlib
import json
from config import valkey
from langchain_core.messages import AIMessage

def get_answer_cache_key(prompt, memory_context="", skill_context=""):
    """
    Generate MD5-based cache key for storing/retrieving answers.
    Includes memory and skill context to ensure personalized answers are cached correctly.
    """
    clean_p = prompt.strip().lower()
    m_ctx = (memory_context or "").strip()
    s_ctx = (skill_context or "").strip()
    
    # Combine all elements that affect the answer into the hash
    key_base = f"prompt:{clean_p}|mem:{m_ctx}|skill:{s_ctx}"
    return f"answer_cache:{hashlib.md5(key_base.encode()).hexdigest()}"


def cache_check_node(state):
    """
    Checks Valkey cache for a pre-computed answer.
    Returns cache_hit=True with the answer if found,
    or cache_hit=False to continue the pipeline.
    """
    user_prompt = state.get("prompt", "")
    memory_context = state.get("memory_context", "")
    skill_context = state.get("skill_context", "")

    # We still skip cache for uploaded files because they are session-specific 
    # and can be large/complex to hash reliably as part of the key.
    if state.get("uploaded_files_available"):
        print("DEBUG: Skipping cache because uploaded files are available in session.")
        return {"cache_hit": False}

    print(f"DEBUG: cache_check_node received prompt: '{user_prompt}'")
    
    # Try to fetch from Valkey
    if valkey:
        cache_key = get_answer_cache_key(user_prompt, memory_context, skill_context)
        print(f"DEBUG: Checking cache key: {cache_key}")
        try:
            raw_cached = valkey.get(cache_key)
            if raw_cached:
                print(f"🚀 Valkey Hit: Instant response for '{user_prompt[:30]}...'")
                
                # Handle both plain string (legacy) and JSON-encoded (new) cache values
                try:
                    cached_data = json.loads(raw_cached)
                    if isinstance(cached_data, dict):
                        answer = cached_data.get("final_answer", "")
                        # Return all cached metadata (diagram_svg, intent, etc.)
                        return {
                            **cached_data,
                            "messages": [AIMessage(content=answer)],
                            "cache_hit": True
                        }
                except json.JSONDecodeError:
                    # Fallback for plain string answers
                    return {
                        "final_answer": raw_cached, 
                        "messages": [AIMessage(content=raw_cached)],
                        "cache_hit": True
                    }
            else:
                print(f"DEBUG: Cache miss for '{user_prompt[:30]}...'")
        except Exception as e:
            print(f"Valkey Cache Read Error: {e}")
            
    return {"cache_hit": False}
