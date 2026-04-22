from config import model, valkey
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import inspect
import hashlib
from prompts.prompts import answer_system_prompt

def get_answer_cache_key(prompt):
    clean_p = prompt.strip().lower()
    return f"answer_cache:{hashlib.md5(clean_p.encode()).hexdigest()}"

async def answer_node(state, config=None):

    # -------------------------------
    # Read state safely
    # -------------------------------

    user_prompt = state["prompt"]
    memory_context = (state.get("memory_context") or "").strip()
    sub_queries = state.get("sub_queries", [])
    retrieved_chunks = state.get("retrieved_chunks", [])
    retrieved_documents = state.get("retrieved_documents", [])
    urls = state.get("search_results", [])
    intent = state.get("intent")

    # -------------------------------
    # Format retrieved chunks
    # -------------------------------

    if retrieved_chunks:
        print(f".......Formatting {len(retrieved_chunks)} chunks for answer.......")
        chunks_text = "\n\n".join(
            f"Chunk {i + 1}: {chunk}"
            for i, chunk in enumerate(retrieved_chunks)
        )
    else:
        print("⚠️ No chunks found for answer generation. Using base knowledge.")
        chunks_text = "No external context was retrieved. Answer using your own knowledge."

    # -------------------------------
    # Format sub queries
    # -------------------------------

    if sub_queries:
        sub_queries_text = "\n".join(map(str, sub_queries))
    else:
        sub_queries_text = "No sub queries were generated."

    # -------------------------------
    # Format urls
    # -------------------------------

    if urls:
        cleaned_urls = []
        for item in urls:
            if isinstance(item, dict):
                if "url" in item:
                    title = item.get("title", "Source")
                    cleaned_urls.append(f"{title}: {item['url']}")
                elif "link" in item:
                    cleaned_urls.append(item["link"])
                else:
                    cleaned_urls.append(str(item))
            else:
                cleaned_urls.append(str(item))
        urls_text = "\n".join(cleaned_urls)
    elif retrieved_documents:
        cleaned_urls = []
        for item in retrieved_documents:
            if not isinstance(item, dict):
                continue
            title = item.get("title", "Uploaded Document")
            url = item.get("url", "")
            if url:
                cleaned_urls.append(f"{title}: {url}")
            else:
                cleaned_urls.append(str(title))
        urls_text = "\n".join(cleaned_urls) if cleaned_urls else "No sources available."
    else:
        urls_text = "No sources available."

    # -------------------------------
    # Prompt template
    # -------------------------------

    prompt = ChatPromptTemplate.from_messages([
        ("system", answer_system_prompt),
        (
            "human",
            """
Original Prompt:
{prompt}

Sub Queries:
{sub_queries}

Context:
{chunks}

Add inline citations per sentence.
Add all sources and references at the end.

Sources:
{urls}

Private User Memory Context (for personalization, hidden from user unless directly relevant):
{memory_context}

Positive Prompt :
- Giving more content
"""
        )
    ])

    formatted_prompt = prompt.format_messages(
        prompt=user_prompt,
        sub_queries=sub_queries_text,
        chunks=chunks_text,
        urls=urls_text,
        memory_context=memory_context or "No user memory available.",
    )

    chain = model | StrOutputParser()
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    token_callback = configurable.get("token_callback")

    if intent == "pdf":
        print("\n📝 Generating content for PDF (Background processing)...")
        final_answer = await chain.ainvoke(formatted_prompt)
    else:
        print("\n======= Streaming Answer =======\n")
        final_answer = ""
        async for token in chain.astream(formatted_prompt):
            if not token:
                continue
            print(token, end="", flush=True)
            final_answer += token
            if token_callback:
                callback_result = token_callback(token)
                if inspect.isawaitable(callback_result):
                    await callback_result
        print("\n\n======= Done =======\n")

    # -------------------------------
    # Save to Valkey Cache (TTL: 1 Hour)
    # -------------------------------
    if valkey and final_answer and intent not in {"pdf", "diagram", "research_with_diagram"}:
        try:
            cache_key = get_answer_cache_key(user_prompt)
            valkey.setex(cache_key, 3600, final_answer)
        except Exception as e:
            print(f"Valkey Cache Write Error: {e}")

    return {
        "final_answer": final_answer
    }
