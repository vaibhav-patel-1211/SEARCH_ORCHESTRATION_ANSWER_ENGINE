from database.cloud.mongo_atlas_setup import documents
from config import reranker
from flashrank import RerankRequest
from urllib.parse import urlparse

TOP_K = 20
NUM_CANDIDATES = 200
SNIPPET_MAX_LEN = 220


def _derive_title(url: str | None) -> str:
    if not url:
        return "Source"
    parsed = urlparse(url)
    return parsed.netloc or "Source"


def _build_doc_metadata(title: str | None, url: str | None, text: str | None) -> dict:
    snippet = (text or "").strip().replace("\n", " ")
    if len(snippet) > SNIPPET_MAX_LEN:
        snippet = f"{snippet[:SNIPPET_MAX_LEN]}..."

    resolved_title = (title or "").strip() or _derive_title(url)
    return {
        "title": resolved_title,
        "url": (url or "").strip(),
        "snippet": snippet or None,
    }

def reciprocal_rank_fusion(results_list, k=60):
    """
    Combines multiple ranked results using Reciprocal Rank Fusion.
    """
    fused_scores = {}
    for results in results_list:
        for rank, doc in enumerate(results):
            doc_id = doc["_id"]
            if doc_id not in fused_scores:
                fused_scores[doc_id] = {"score": 0.0, "doc": doc}
            fused_scores[doc_id]["score"] += 1.0 / (rank + k)
    
    reranked = sorted(fused_scores.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in reranked]

def retrieve_chunks_node(state):
    query_embeddings = state.get("query_embeddings", [])
    sub_queries = state.get("sub_queries", [])
    prompt = state.get("prompt", "")
    
    search_queries = sub_queries if sub_queries else [prompt]
    depth = state.get("retrieval_limit", 10)

    all_retrieved_docs = []

    print(f".......Starting Hybrid Search for {len(search_queries)} queries.......")

    for i, query_text in enumerate(search_queries):
        if i < len(query_embeddings):
            query_vector = query_embeddings[i]
        else:
            continue

        print(f"🔍 Processing query {i+1}: {query_text[:50]}...")

        # 1. MongoDB Vector Search
        vector_pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": NUM_CANDIDATES,
                    "limit": depth * 2
                }
            }
        ]
        
        # 2. MongoDB Keyword Search (Atlas Search)
        keyword_pipeline = [
            {
                "$search": {
                    "index": "default", 
                    "text": {
                        "query": query_text,
                        "path": "text"
                    }
                }
            },
            {"$limit": depth * 2}
        ]

        try:
            vector_results = list(documents.aggregate(vector_pipeline))
            try:
                keyword_results = list(documents.aggregate(keyword_pipeline))
            except Exception:
                keyword_results = []

            # Fusion
            fused_docs = reciprocal_rank_fusion([vector_results, keyword_results])
            all_retrieved_docs.extend(fused_docs)

        except Exception as e:
            print(f"Search failed for query {i+1}: {e}")

    # Deduplicate by _id
    unique_docs_dict = {doc["_id"]: doc for doc in all_retrieved_docs}
    unique_docs = list(unique_docs_dict.values())

    if not unique_docs:
        print("⚠️ No chunks retrieved from database.")
        return {"retrieved_chunks": [], "retrieved_documents": [], "rag_done": True}

    print(f"Total retrieved docs before reranking: {len(unique_docs)}")

    # 3. Advanced Reranking (Metadata Injection)
    passages = []
    for doc in unique_docs[:100]:
        contextual_text = f"[Source: {doc.get('url', 'N/A')}] {doc['text']}"
        passages.append({
            "id": doc["_id"], 
            "text": contextual_text, 
            "meta": {
                "url": doc.get("url", "N/A"),
                "title": doc.get("title"),
            }
        })
    
    try:
        request = RerankRequest(query=prompt, passages=passages)
        reranked_results = reranker.rerank(request)[:TOP_K]
        final_chunks = [doc["text"] for doc in reranked_results]
        retrieved_documents = [
            _build_doc_metadata(
                doc.get("meta", {}).get("title"),
                doc.get("meta", {}).get("url"),
                doc.get("text"),
            )
            for doc in reranked_results
        ]
        print(f"✅ Reranking complete. Final chunks: {len(final_chunks)}")
    except Exception as e:
        print(f"❌ Reranking failed: {e}. Using unique retrieved chunks.")
        fallback_docs = unique_docs[:TOP_K]
        final_chunks = [doc["text"] for doc in fallback_docs]
        retrieved_documents = [
            _build_doc_metadata(doc.get("title"), doc.get("url"), doc.get("text"))
            for doc in fallback_docs
        ]

    return {
        "retrieved_chunks": final_chunks,
        "retrieved_documents": retrieved_documents,
        "rag_done": True,
    }
