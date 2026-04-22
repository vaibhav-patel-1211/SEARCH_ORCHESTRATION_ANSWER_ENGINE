import re

from langchain_core.prompts import ChatPromptTemplate

from config import model
from prompts.prompts import planner_system_prompt
from schemas.planner_schema import ExecutionPlan

_CODING_ACTION_RE = re.compile(
    r"\b(code|implement|write|build|create|fix|debug|refactor|optimize|test|script|function|class|endpoint|api|regex|algorithm|bug|error|exception|traceback)\b",
    re.IGNORECASE,
)
_CODING_TECH_RE = re.compile(
    r"\b(python|javascript|typescript|java|c\+\+|c#|go|rust|sql|html|css|react|node|fastapi|django|flask|pandas|numpy|langchain|langgraph)\b",
    re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.IGNORECASE)


def _is_coding_fast_path(query: str) -> bool:
    text = (query or "").strip()
    if not text:
        return False
    if _CODE_FENCE_RE.search(text):
        return True
    if "traceback" in text.lower() or "stack trace" in text.lower():
        return True
    return bool(_CODING_ACTION_RE.search(text) and _CODING_TECH_RE.search(text))


async def planner_node(state):
    prompt = state["prompt"]
    user_requested_research = bool(state.get("research_enabled", False))

    if _is_coding_fast_path(prompt):
        return {
            "intent": "coding",
            "planner_reasoning": "Fast-path routing: coding query detected by heuristic classifier.",
            "sub_queries": [],
            "max_search_results": 0,
            "retrieval_limit": 0,
            "research_enabled": False,
        }
    
    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", planner_system_prompt),
        ("human", "{query}")
    ])
    
    # Use with_structured_output for reliable planning
    structured_llm = model.with_structured_output(ExecutionPlan)
    chain = planner_prompt | structured_llm
    
    plan = await chain.ainvoke({"query": prompt})
    
    print("\n" + "="*50)
    print("🤖 AGENTIC REASONING:")
    print(plan.reasoning)
    print(f"📊 Strategy: Intent={plan.intent}, Breadth={plan.max_search_results}, Depth={plan.retrieval_limit}, Research={plan.research_enabled}")
    
    if plan.sub_queries:
        print("\n🔍 Generated Sub-Queries:")
        for i, q in enumerate(plan.sub_queries, 1):
            print(f"   {i}. {q}")
            
    print("="*50 + "\n")

    resolved_research_enabled = bool(plan.research_enabled) and user_requested_research

    return {
        "intent": plan.intent,
        "planner_reasoning": plan.reasoning,
        "sub_queries": plan.sub_queries,
        "max_search_results": plan.max_search_results,
        "retrieval_limit": plan.retrieval_limit,
        "research_enabled": resolved_research_enabled
    }
