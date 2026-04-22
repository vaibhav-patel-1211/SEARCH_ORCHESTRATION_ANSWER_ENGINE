from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text_node(state):
    """
    Takes cleaned text from state and splits into semantic chunks with context headers.
    Stores result in state as 'chunks_with_meta'.
    """
    print(".......Contextual Chunking Text.......")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks_with_meta = []

    # state["clean_text"] -> {url: full_text}
    clean_text_data = state.get("clean_text", {})
    if not clean_text_data:
        print("⚠️ No clean text available for chunking.")
        return {"chunks_with_meta": []}

    for url, text in clean_text_data.items():
        # Prepend a context header to help the Reranker and LLM identify sources
        source_context = f"[Source: {url}]\n"
        
        raw_chunks = splitter.split_text(text)
        for chunk in raw_chunks:
            chunks_with_meta.append({
                "text": source_context + chunk,
                "url": url
            })

    print(f".......Generated {len(chunks_with_meta)} contextual chunks.......")
    return {"chunks_with_meta": chunks_with_meta}
