from __future__ import annotations

import math
from urllib.parse import quote

from flashrank import RerankRequest

from config import reranker
from database.cloud.mongo_atlas_setup import uploaded_document_chunks

TOP_K = 20
NUM_CANDIDATES = 200
SNIPPET_MAX_LEN = 220
LOCAL_FALLBACK_LIMIT = 2500


def _build_doc_metadata(filename: str, file_id: str, text: str | None) -> dict:
    snippet = (text or "").strip().replace("\n", " ")
    if len(snippet) > SNIPPET_MAX_LEN:
        snippet = f"{snippet[:SNIPPET_MAX_LEN]}..."

    return {
        "title": filename or "Uploaded Document",
        "url": f"uploaded://{quote(file_id)}",
        "snippet": snippet or None,
    }


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0

    length = min(len(vec_a), len(vec_b))
    if length == 0:
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for idx in range(length):
        a = float(vec_a[idx])
        b = float(vec_b[idx])
        dot += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _keyword_bonus(query_text: str, chunk_text: str) -> float:
    query_terms = [token for token in query_text.lower().split() if len(token) > 2]
    if not query_terms:
        return 0.0

    lowered_chunk = chunk_text.lower()
    hits = sum(1 for term in query_terms if term in lowered_chunk)
    return min(hits * 0.03, 0.3)


def retrieve_uploaded_chunks_node(state):
    query_embeddings = state.get("query_embeddings", [])
    sub_queries = state.get("sub_queries", [])
    prompt = state.get("prompt", "")
    session_id = state.get("session_id", "")
    user_id = state.get("user_id", "")
    uploaded_files = state.get("uploaded_files", [])
    depth = state.get("retrieval_limit", 10)

    if not session_id:
        print("⚠️ No session_id in state. Skipping document retrieval.")
        return {"retrieved_chunks": [], "retrieved_documents": [], "rag_done": True}

    allowed_file_ids = [
        file.get("file_id")
        for file in uploaded_files
        if isinstance(file, dict) and file.get("file_id")
    ]
    
    if not allowed_file_ids:
        print(f"⚠️ No allowed_file_ids for session {session_id}. Skipping document retrieval.")
        return {"retrieved_chunks": [], "retrieved_documents": [], "rag_done": True}

    print(f"🔍 Retrieving from {len(allowed_file_ids)} files for session {session_id}...")

    search_queries = sub_queries if sub_queries else [prompt]
    all_docs = []
    
    # Use file_ids and user_id for the base filter. 
    # session_id is removed from here because file_id is already session-scoped in our local DB metadata,
    # and removing it from Atlas filter makes it more resilient to session migration or mismatches.
    base_filter = {"file_id": {"$in": allowed_file_ids}}
    if user_id:
        base_filter["user_id"] = user_id

    # Pre-fetch candidates for local fallback in case Atlas Search is unavailable
    try:
        fallback_candidates = list(
            uploaded_document_chunks.find(
                base_filter,
                {
                    "_id": 1,
                    "file_id": 1,
                    "filename": 1,
                    "text": 1,
                    "embedding": 1,
                },
            ).limit(LOCAL_FALLBACK_LIMIT)
        )
        print(f"📂 Found {len(fallback_candidates)} local fallback candidates.")
    except Exception as e:
        print(f"❌ Local fallback fetch failed: {e}")
        fallback_candidates = []

    for idx, query_text in enumerate(search_queries):
        query_vector = query_embeddings[idx] if idx < len(query_embeddings) else None
        
        if query_vector:
            # 1. Atlas Vector Search
            vector_pipeline = [
                {
                    "$vectorSearch": {
                        "index": "uploaded_vector_index",
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": NUM_CANDIDATES,
                        "limit": depth * 3,
                        "filter": base_filter,
                    }
                }
            ]
            try:
                vector_results = list(uploaded_document_chunks.aggregate(vector_pipeline))
                if vector_results:
                    print(f"✅ Vector search found {len(vector_results)} docs for query {idx+1}")
                    all_docs.extend(vector_results)
            except Exception as e:
                # Log error details to help diagnose Atlas index issues
                err_msg = str(e)
                if "dimension" in err_msg.lower():
                    print(f"❌ Atlas Vector Search Dimension Mismatch: {err_msg}")
                elif "index" in err_msg.lower():
                    print(f"❌ Atlas Vector Search Index missing or invalid: {err_msg}")
                else:
                    print(f"⚠️ Vector search error for query {idx+1}: {err_msg[:100]}...")

        # 2. Atlas Keyword Search
        # Build file_id filter for keyword search
        file_id_filter = []
        if len(allowed_file_ids) == 1:
            file_id_filter = [{"phrase": {"query": allowed_file_ids[0], "path": "file_id"}}]
        else:
            # Multiple file IDs: use 'should' which acts as 'OR'
            file_id_filter = [
                {
                    "compound": {
                        "should": [
                            {"phrase": {"query": fid, "path": "file_id"}} for fid in allowed_file_ids
                        ],
                        "minimumShouldMatch": 1
                    }
                }
            ]

        keyword_pipeline = [
            {
                "$search": {
                    "index": "uploaded_default",
                    "compound": {
                        "must": [
                            {
                                "text": {
                                    "query": query_text,
                                    "path": "text",
                                }
                            },
                        ],
                        "filter": file_id_filter
                    }
                }
            },
            {"$limit": depth * 2},
        ]
        try:
            keyword_results = list(uploaded_document_chunks.aggregate(keyword_pipeline))
            if keyword_results:
                print(f"✅ Keyword search found {len(keyword_results)} docs for query {idx+1}")
                all_docs.extend(keyword_results)
        except Exception as e:
            if "index" in str(e).lower():
                print(f"❌ Atlas Keyword Search Index 'uploaded_default' missing or invalid.")
            # print(f"⚠️ Keyword search failed: {e}")
            pass

        # 3. Local Semantic Fallback (if Atlas search returned nothing or failed)
        if not all_docs and fallback_candidates and query_vector:
            print(f"🔄 Using local semantic fallback for query {idx+1}...")
            scored = []
            for doc in fallback_candidates:
                embedding = doc.get("embedding") or []
                if not isinstance(embedding, list) or not embedding:
                    continue
                text = str(doc.get("text", ""))
                # Manual Cosine Similarity + Keyword Bonus
                score = _cosine_similarity(query_vector, embedding) + _keyword_bonus(query_text, text)
                scored.append((score, doc))

            scored.sort(key=lambda item: item[0], reverse=True)
            top_scored = [doc for _, doc in scored[: depth * 3]]
            all_docs.extend(top_scored)
            if top_scored:
                print(f"✅ Local fallback found {len(top_scored)} docs for query {idx+1}")

    unique_docs = {str(doc.get("_id")): doc for doc in all_docs if isinstance(doc, dict)}
    docs = list(unique_docs.values())
    
    if not docs:
        print("❌ No documents retrieved from any source (Vector, Keyword, or Fallback).")
        return {"retrieved_chunks": [], "retrieved_documents": [], "rag_done": True}

    print(f"📊 Total unique chunks collected: {len(docs)}")

    passages = []
    for doc in docs[:100]:
        filename = str(doc.get("filename", "Uploaded Document"))
        text = str(doc.get("text", ""))
        passages.append(
            {
                "id": str(doc.get("_id", "")),
                "text": f"[Document: {filename}] {text}",
                "meta": {
                    "file_id": str(doc.get("file_id", "")),
                    "filename": filename,
                },
            }
        )

    try:
        request = RerankRequest(query=prompt, passages=passages)
        reranked = reranker.rerank(request)[:TOP_K]
        final_chunks = [item["text"] for item in reranked]
        retrieved_documents = [
            _build_doc_metadata(
                filename=item.get("meta", {}).get("filename", "Uploaded Document"),
                file_id=item.get("meta", {}).get("file_id", ""),
                text=item.get("text"),
            )
            for item in reranked
        ]
        print(f"✅ Reranking complete. {len(final_chunks)} chunks selected.")
    except Exception as e:
        print(f"⚠️ Reranking failed: {e}. Using top retrieved docs as fallback.")
        fallback = passages[:TOP_K]
        final_chunks = [item["text"] for item in fallback]
        retrieved_documents = [
            _build_doc_metadata(
                filename=item.get("meta", {}).get("filename", "Uploaded Document"),
                file_id=item.get("meta", {}).get("file_id", ""),
                text=item.get("text"),
            )
            for item in fallback
        ]

    return {
        "retrieved_chunks": final_chunks,
        "retrieved_documents": retrieved_documents,
        "rag_done": True,
    }

