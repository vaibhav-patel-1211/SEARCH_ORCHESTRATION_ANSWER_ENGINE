"""
planner.py - The "brain" of the pipeline.
Analyzes user intent and decides:
  - Is this a coding question? (fast-path regex check)
  - What sub-queries to generate for search
  - How broad/deep the search should be
  - Whether research mode is needed

Uses structured output from the LLM to get a reliable ExecutionPlan.
"""

import re

from langchain_core.prompts import ChatPromptTemplate

from config import model
from prompts.prompts import planner_system_prompt
from schemas.planner_schema import ExecutionPlan

# Regex to find coding-related action words in the prompt
_CODING_ACTION_RE = re.compile(
    r"\b(code|implement|write|build|create|fix|debug|refactor|optimize|test|script|function|class|endpoint|api|regex|algorithm|bug|error|exception|traceback)\b",
    re.IGNORECASE,
)

# Regex to find technology/language names in the prompt
_CODING_TECH_RE = re.compile(
    r"\b(python|javascript|typescript|java|c\+\+|c#|go|rust|sql|html|css|react|node|fastapi|django|flask|pandas|numpy|langchain|langgraph)\b",
    re.IGNORECASE,
)

# Detects if user pasted a code block (triple backticks)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.IGNORECASE)


def _is_coding_fast_path(query: str) -> bool:
    """
    Quick heuristic check to detect coding queries WITHOUT calling the LLM.
    Saves time and tokens for obvious coding questions.
    Returns True if the query looks like a coding task.
    """
    text = (query or "").strip()

    if not text:
        return False

    # If user pasted code (has triple backticks), it's definitely coding
    if _CODE_FENCE_RE.search(text):
        return True

    # Python/JS error traces are coding queries
    if "traceback" in text.lower() or "stack trace" in text.lower():
        return True

    # Need BOTH a coding action word AND a tech name to classify as coding
    # This avoids false positives like "write a poem" or "what is python" (no action)
    return bool(_CODING_ACTION_RE.search(text) and _CODING_TECH_RE.search(text))


async def planner_node(state):
    """
    Main planner node. First tries fast-path for coding queries,
    then falls back to LLM-based planning with structured output.
    """
    prompt = state["prompt"]
    user_requested_research = bool(state.get("research_enabled", False))

    # Fast path: skip LLM call entirely for obvious coding queries
    if _is_coding_fast_path(prompt):
        return {
            "intent": "coding",
            "planner_reasoning": "Fast-path routing: coding query detected by heuristic classifier.",
            "sub_queries": [],
            "max_search_results": 0,
            "retrieval_limit": 0,
            "research_enabled": False,
        }

    # For non-coding queries, ask the LLM to plan the execution strategy
    system_prompt = planner_system_prompt

    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}")
    ])

    # with_structured_output forces the LLM to return a valid ExecutionPlan schema
    structured_llm = model.with_structured_output(ExecutionPlan)
    chain = planner_prompt | structured_llm

    plan = await chain.ainvoke({"query": prompt})

    # Log the plan for debugging
    print("\n" + "="*50)
    print("🤖 AGENTIC REASONING:")
    print(plan.reasoning)
    print(f"📊 Strategy: Intent={plan.intent}, Breadth={plan.max_search_results}, Depth={plan.retrieval_limit}, Research={plan.research_enabled}")

    if plan.sub_queries:
        print("\n🔍 Generated Sub-Queries:")
        for i, q in enumerate(plan.sub_queries, 1):
            print(f"   {i}. {q}")

    print("="*50 + "\n")

    # Only enable research if BOTH the planner and user agree
    resolved_research_enabled = bool(plan.research_enabled) and user_requested_research

    return {
        "intent": plan.intent,
        "planner_reasoning": plan.reasoning,
        "sub_queries": plan.sub_queries,
        "max_search_results": plan.max_search_results,
        "retrieval_limit": plan.retrieval_limit,
        "research_enabled": resolved_research_enabled
    }
