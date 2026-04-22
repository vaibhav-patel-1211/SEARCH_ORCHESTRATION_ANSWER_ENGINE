import asyncio
import time
import json
import hashlib
from urllib.parse import urlparse
from ddgs import DDGS  # Ensure you have: pip install duckduckgo_search
from config import valkey

# ---------------- CONFIGURATION ----------------

SEMAPHORE_LIMIT = 20
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

CACHE_EXPIRY = 3600  # Cache for 1 hour

# ---------------- HELPERS ----------------

def normalize_url(url):
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    except Exception:
        return url.rstrip("/")

def get_cache_key(query):
    """Generate a stable key for caching."""
    clean_q = query.strip().lower()
    return f"search_cache:{hashlib.md5(clean_q.encode()).hexdigest()}"

# ---------------- SEARCH FUNCTIONS ----------------

async def search_ddgs_optimized(query, max_results=2, timeout=10):
    """
    Runs a single search with caching and concurrency lock.
    """
    # 1. Check Valkey Cache
    cache_key = get_cache_key(query)
    if valkey:
        try:
            cached = valkey.get(cache_key)
            if cached:
                # print(f"🚀 Valkey Hit (Search): {query[:30]}...")
                return json.loads(cached)
        except Exception as e:
            print(f"Valkey Read Error: {e}")

    urls = []
    async with semaphore:
        try:
            def _blocking_search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))

            results = await asyncio.wait_for(
                asyncio.to_thread(_blocking_search),
                timeout=timeout
            )
            urls = [r.get("href", "") for r in results if r.get("href")]

        except asyncio.TimeoutError:
            print(f"Timeout skipping query: '{query}'")
        except Exception as e:
            print(f"Error searching '{query}': {e}")

    res = {"query": query, "urls": urls}

    # 2. Store in Valkey Cache
    if valkey and urls:
        try:
            valkey.setex(cache_key, CACHE_EXPIRY, json.dumps(res))
        except Exception as e:
            print(f"Valkey Write Error: {e}")

    return res


# ---------------- BATCH PROCESSING ----------------

async def async_ddgs_search_optimized(queries, max_results=5):
    tasks = [search_ddgs_optimized(q, max_results) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]

# ---------------- DEDUPLICATION ----------------

def deduplicate_results_optimized(results):
    seen_urls = {}
    clean_results = []
    for item in results:
        if not item.get("urls"): continue
        unique_urls = []
        for url in item["urls"]:
            if not url: continue
            norm_url = normalize_url(url)
            if norm_url not in seen_urls:
                seen_urls[norm_url] = True
                unique_urls.append(url)
        if unique_urls:
            clean_results.append({"query": item["query"], "urls": unique_urls})
    return clean_results

# ---------------- MAIN PIPELINE ----------------

async def orchestrated_search_async_optimized(sub_queries, max_results=5):
    start_time = time.time()
    print(f"Starting search for {len(sub_queries)} queries...")
    raw_results = await async_ddgs_search_optimized(sub_queries, max_results=max_results)
    clean_results = deduplicate_results_optimized(raw_results)
    elapsed = time.time() - start_time
    print(f"Search completed in {elapsed:.2f} seconds. Found results for {len(clean_results)} queries.")
    return clean_results

async def orchestrated_search_async(sub_queries, max_results=2):
    return await orchestrated_search_async_optimized(sub_queries, max_results)
