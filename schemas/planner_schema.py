from typing import List, Literal
from pydantic import BaseModel, Field

class ExecutionPlan(BaseModel):
    reasoning: str = Field(description="Internal monologue: Why are we taking this approach and how deep should we go?")
    intent: Literal[
        "research",
        "research_with_diagram",
        "diagram",
        "coding",
        "calculation",
        "transformation",
        "recommendation",
        "how_to",
        "general",
        "question_answer",
        "pdf",
    ] = Field(description="User query intent")
    sub_queries: List[str] = Field(description="Decomposed search queries for research. Empty if research is not needed.")
    
    # Agentic Controls
    max_search_results: int = Field(default=3, description="Breadth: 1-10 websites to search per query.")
    retrieval_limit: int = Field(default=5, description="Depth: 5-20 chunks to retrieve for context.")
    research_enabled: bool = Field(default=True, description="True if external search is needed.")
