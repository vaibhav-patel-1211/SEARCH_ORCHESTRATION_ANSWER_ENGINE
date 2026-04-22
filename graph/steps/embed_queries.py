from config import embedding_model, model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from prompts.prompts import hyde_system_prompt

def generate_hypothetical_answer(query):
    """
    HyDE: Generate a brief hypothetical answer to improve embedding relevance.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", hyde_system_prompt),
        ("human", "{query}")
    ])
    chain = prompt | model | StrOutputParser()
    try:
        # We want a quick, small answer
        return chain.invoke({"query": query})
    except Exception as e:
        print(f"⚠️ HyDE generation failed for '{query[:20]}...': {e}")
        return query # Fallback to original query

def embed_queries_node(state):
    sub_queries = state.get("sub_queries", [])
    prompt = state.get("prompt", "")
    
    # If no sub_queries, use the original prompt
    original_queries = sub_queries if sub_queries else [prompt]

    print(f".......Expanding {len(original_queries)} queries with HyDE.......")

    hyde_queries = []
    for q in original_queries:
        # Combine the original query with its hypothetical answer
        # This gives the embedding model both the question and the "expected" answer text
        hypothetical = generate_hypothetical_answer(q)
        hyde_queries.append(f"Query: {q}\nAnswer: {hypothetical}")

    print("Embedding HyDE expanded queries...")

    try:
        vectors = embedding_model.embed_documents(hyde_queries) 
        print(f"Generated {len(vectors)} query vectors with HyDE.")
        return {"query_embeddings": vectors}
    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        try:
            fallback_vectors = [embedding_model.embed_query(q) for q in original_queries]
            print(f"✅ Fallback query embeddings generated: {len(fallback_vectors)}")
            return {"query_embeddings": fallback_vectors}
        except Exception as fallback_error:
            print(f"❌ Fallback embedding failed: {fallback_error}")
            return {"query_embeddings": []}
