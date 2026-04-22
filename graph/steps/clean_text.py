import asyncio
import os
import trafilatura
from utils.timeout_utils import retry_async

# ---------------- SINGLE CLEAN FUNCTION ----------------

@retry_async(max_attempts=2, delay=1)
async def _single_clean_async(url: str):
    """
    Fetch and extract main readable text from a URL using trafilatura.
    Wrapped with retry and runs in a thread to not block.
    """
    try:
        # Wrap the blocking trafilatura call in a timeout
        def _fetch():
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None
            return trafilatura.extract(
                downloaded,
                include_links=False,
                include_images=False,
                include_comments=False,
                favor_precision=False,
                favor_recall=True
            )

        return await asyncio.wait_for(
            asyncio.to_thread(_fetch),
            timeout=15 # 15 second timeout per URL
        )
    except asyncio.TimeoutError:
        print(f"🕒 Timeout scraping {url}")
        return None
    except Exception as e:
        print(f"⚠️ Error scraping {url}: {e}")
        return None

# ---------------- ASYNC MULTI CLEAN (PARALLEL) ----------------

async def clean_multiple_urls(urls, workers=20):
    """
    Clean multiple URLs in parallel and return a dict:
    { url : cleaned_text }
    """
    if not urls:
        print("⚠️ No URLs found to clean.")
        return {}

    print(f".......Cleaning {len(urls)} URLs in parallel (with retries).......")
    semaphore = asyncio.Semaphore(workers)

    async def sem_clean(url):
        async with semaphore:
            return await _single_clean_async(url)

    # create tasks
    tasks = [sem_clean(url) for url in urls]

    # run all in parallel
    results = await asyncio.gather(*tasks)

    # build dict (url -> clean text)
    clean_data = {}

    for url, content in zip(urls, results):
        if content:   # skip failed fetches
            clean_data[url] = content

    return clean_data


# ---------------- TEST ----------------

if __name__ == "__main__":

    async def main():

        urls = [
            "https://www.ibm.com/think/topics/machine-learning",
            "https://en.wikipedia.org/wiki/Machine_learning",
            "https://www.geeksforgeeks.org/machine-learning/"
        ]

        cleaned = await clean_multiple_urls(urls)

        print("\n✅ CLEANED CONTENT:\n")

        for url, text in cleaned.items():
            print("🌐 URL:", url)
            print("\n📄 CONTENT PREVIEW:\n")
            print(text[:600])   # show first 600 chars
            print("\n--------------------------\n")

    asyncio.run(main())




# =====================================
# firecrawl
# ====================================
# import asyncio
# import aiohttp

# # ---------------- CONFIG ----------------

# FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v2/scrape"


# # ---------------- SINGLE CLEAN FUNCTION ----------------

# def _single_clean(url: str):
#     """
#     (Sync wrapper for compatibility - not used directly)
#     Kept only so other files don't break if imported.
#     """
#     raise NotImplementedError(
#         "Use async pipeline clean_multiple_urls with Firecrawl"
#     )


# # ---------------- ASYNC MULTI CLEAN (PARALLEL) ----------------

# async def clean_multiple_urls(urls, workers=20):
#     """
#     Clean multiple URLs in parallel using Firecrawl.
#     Returns:
#         { url : cleaned_text }
#     """

#     connector = aiohttp.TCPConnector(limit=workers)

#     headers = {
#         "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
#         "Content-Type": "application/json"
#     }

#     async with aiohttp.ClientSession(
#         connector=connector,
#         headers=headers
#     ) as session:

#         semaphore = asyncio.Semaphore(workers)

#         async def sem_clean(url):

#             payload = {
#                 "url": url,
#                 "formats": ["markdown"],      # best for LLM/RAG
#                 "onlyMainContent": True,
#                 "maxAge": 86400000            # cache for 1 day (save credits)
#             }

#             async with semaphore:

#                 try:
#                     async with session.post(
#                         FIRECRAWL_API_URL,
#                         json=payload,
#                         timeout=aiohttp.ClientTimeout(total=60)
#                     ) as resp:

#                         data = await resp.json()

#                         if data.get("success"):
#                             return data["data"]["markdown"]

#                         else:
#                             print(f"❌ Firecrawl failed for {url}")
#                             return None

#                 except Exception as e:
#                     print(f"⚠️ Error for {url}: {e}")
#                     return None

#         # Create parallel tasks
#         tasks = [sem_clean(url) for url in urls]

#         # Run in parallel
#         results = await asyncio.gather(*tasks)

#     # Build output dict (same format as before)
#     clean_data = {}

#     for url, content in zip(urls, results):
#         if content:
#             clean_data[url] = content

#     return clean_data


# # ---------------- TEST ----------------

# if __name__ == "__main__":

#     async def main():

#         urls = [
#             "https://www.ibm.com/think/topics/machine-learning",
#             "https://en.wikipedia.org/wiki/Machine_learning",
#             "https://www.geeksforgeeks.org/machine-learning/"
#         ]

#         cleaned = await clean_multiple_urls(urls)

#         print("\n✅ CLEANED CONTENT:\n")

#         for url, text in cleaned.items():
#             print("🌐 URL:", url)
#             print("\n📄 CONTENT PREVIEW:\n")
#             print(text[:600])
#             print("\n--------------------------\n")

#     asyncio.run(main())
