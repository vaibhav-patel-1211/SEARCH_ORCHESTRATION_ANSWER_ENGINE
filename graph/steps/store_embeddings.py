from dotenv import load_dotenv
load_dotenv()

import hashlib
from config import embedding_model
from database.cloud.mongo_atlas_setup import documents
from pymongo.errors import BulkWriteError

def embed_and_store_node(state):
    chunks_with_meta = state.get("chunks_with_meta", []) 
    tags = state.get("tags", [])

    if not chunks_with_meta:
        print("⚠️ No chunks with metadata received for embedding")
        return {}

    texts = [c["text"] for c in chunks_with_meta]
    urls = [c["url"] for c in chunks_with_meta]

    print(f".......Embedding {len(texts)} chunks.......")

    try:
        vectors = embedding_model.embed_documents(texts)
    except Exception as e:
        print("Embedding failed:", e)
        return {}

    if not vectors:
        print("No embeddings returned")
        return {}

    docs = []
    for text, url, vector in zip(texts, urls, vectors):
        chunk_id = hashlib.md5(text.encode()).hexdigest()

        docs.append({
            "_id": chunk_id,
            "text": text,
            "url": url,
            "embedding": vector,
            "tags": tags,
            "source_type": "web",
        })

    print(f".......Attempting to store {len(docs)} documents in MongoDB.......")
    try:
        documents.insert_many(docs, ordered=False)
        print(f"Successfully stored {len(docs)} chunks in Mongo")
    except BulkWriteError:
        # Ignore duplicate key errors
        pass
    except Exception as e:
        print("Mongo insert failed:", e)

    print(".......Storage step finished.......")
    return {}
