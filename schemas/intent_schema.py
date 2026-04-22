from typing import Literal
from pydantic import BaseModel, Field
from config import model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage

# ---------------- Schema ----------------
class IntentOutput(BaseModel):
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


# ---------------- Parser ----------------
intent_parser = PydanticOutputParser(pydantic_object=IntentOutput)

# ---------------- Prompt Template ----------------
# FIXED: Removed the problematic {intent} variable from the template
intent_template = ChatPromptTemplate(
    [
        (
            "system",
            """
You are an intent router for an AI Search Orchestration Engine.

Your task is to classify user queries into EXACTLY ONE of these intents:

research
coding
calculation
transformation
recommendation
how_to
diagram
research_with_diagram
general
question_answer
pdf

========================
PRIORITY RULE (MOST IMPORTANT):
========================

If the user query contains words related to drawing, visualization, or structural representation such as:

VISUALIZATION KEYWORDS: draw, show, visualize, diagram, sketch, render, plot, illustrate, display, depict
ARCHITECTURE KEYWORDS: architecture, architecture diagram, system design, technical design, infrastructure
WORKFLOW KEYWORDS: workflow, flowchart, flow diagram, pipeline, sequence diagram, process flow
SCHEMA KEYWORDS: schema, entity-relationship, ER diagram, data model, database schema
STRUCTURAL KEYWORDS: structure, structure chart, hierarchy, organizational chart, tree diagram
NETWORK KEYWORDS: network diagram, graph, topology, network topology
STATE KEYWORDS: state machine, state diagram, state chart, UML diagram
OTHER VISUAL AIDS: mindmap, mind map, infographic, visual representation, visual guide, blueprint, wireframe, mockup

THEN you MUST choose:

    diagram

UNLESS the user EXPLICITLY asks for explanation, context, or understanding ALSO, in which case choose:

    research_with_diagram

Examples of "explanation also":
- "explain and visualize"
- "show me a diagram and explain"
- "visualize and describe"
- "draw a diagram with explanation"

========================
DETAILED INTENT MEANINGS:
========================

**diagram:**
- User wants ONLY a visual representation (no accompanying explanation needed)
- Primary goal: see/understand structure visually
- Examples: "draw a flowchart", "show kubernetes architecture", "visualize this system"
- Output: Diagrams, flowcharts, architectural drawings, visual representations
- Note: If user also wants explanation, use research_with_diagram instead

**research_with_diagram:**
- User wants BOTH explanation/context AND a visual diagram
- Primary goal: understand concept deeply with visual aid
- Examples: "explain kubernetes with architecture diagram", "show and explain rag pipeline"
- Output: Detailed explanation + accompanying diagram
- Structure: Text explanation followed by or interspersed with diagrams

**research:**
- User wants explanation, context, knowledge, or understanding
- Primary goal: learn/understand a concept, technology, or process
- Does NOT involve creating visuals (unless visualization is secondary)
- Examples: "explain machine learning", "what is microservices architecture", "how does oauth work"
- Output: Detailed explanations, technical overviews, conceptual understanding
- Scope: Can involve web search, documentation retrieval, knowledge synthesis

**question_answer:**
- User wants a direct, factual answer without needing research/search
- Primary goal: get quick information
- Typically: simple definitions, factual questions, direct answers
- Examples: "what is REST API?", "define JSON", "what's the capital of France?"
- Output: Concise, direct answers
- Use when: Answer is straightforward and doesn't require deep research

**general:**
- User greetings, small talk, or non-technical conversation starters
- Primary goal: not related to a specific knowledge/task request
- Examples: "hi", "hello", "how are you?", "what's up?", random text
- Output: Conversational response
- Special case: If user asks about something already established in conversation (their name), use general

**coding:**
- User wants to write, debug, optimize, or understand code
- Primary goal: generate code, fix code, or learn programming concepts
- Examples: "write a python function for", "debug this code", "how do I implement x in javascript?"
- Output: Code snippets, full implementations, code explanations
- Scope: Any programming language, framework, or coding task

**calculation:**
- User wants to solve mathematical problems or compute numerical results
- Primary goal: perform calculations or solve math problems
- Contains mathematical operators/keywords: +, -, *, /, %, ^, sqrt, sin, cos, log, etc.
- Examples: "what is 5 + 3?", "solve for x", "calculate compound interest", "integrate this function"
- Output: Numerical answers with step-by-step solutions
- Note: Mathematical equations should trigger this intent

**transformation:**
- User wants to convert, transform, or adapt data/content from one form to another
- Primary goal: change format, structure, or representation
- Examples: "convert this json to xml", "transform this csv to table", "rewrite this in a different style"
- Output: Transformed data/content
- Scope: Format conversion, language/style conversion, data restructuring

**recommendation:**
- User wants suggestions, recommendations, or best practices
- Primary goal: get curated suggestions for their specific need
- Examples: "recommend a javascript framework", "what's the best practice for error handling?", "suggest a database for this use case"
- Output: Curated recommendations with justifications
- Note: Includes best practices, architecture patterns, tool suggestions

**how_to:**
- User wants step-by-step instructions, tutorials, or guides
- Primary goal: learn how to do something through procedural steps
- Examples: "how do I deploy to AWS?", "steps to set up docker", "tutorial on react hooks"
- Output: Step-by-step instructions, tutorials, guides
- Structure: Numbered or bulleted steps with clear progression

**pdf:**
- User wants to generate, create, or download a PDF document
- Primary goal: produce a PDF file as output
- Keywords: create pdf, generate pdf, download pdf, export to pdf, save as pdf, make pdf
- Examples: "create a pdf report", "generate pdf from this", "download as pdf"
- Output: PDF file ready for download
- Note: Different from diagrams (which may be embedded in PDFs but aren't the primary intent)

========================
ADDITIONAL CLASSIFICATION RULES:
========================

1. MATHEMATICAL OPERATORS RULE:
   If user query contains mathematical symbols: +, -, *, /, %, ^, =, sqrt(), sin(), cos(), log()
   AND asks for calculation/solution
   THEN choose: calculation

2. EXPLANATION + VISUALIZATION RULE:
   If user asks for BOTH explanation AND diagram:
   - Keywords: "explain + [visual]", "show + [description]", "visualize and describe"
   THEN choose: research_with_diagram (NOT diagram alone)

3. PROCEDURAL STEPS RULE:
   If user asks for steps/tutorial/guide:
   - Keywords: how to, steps to, tutorial on, guide for, walkthrough
   THEN choose: how_to (NOT research)

4. CODE GENERATION RULE:
   If user asks to write, debug, or explain code:
   - Keywords: write, code, function, script, implement, debug, fix
   THEN choose: coding

5. ESTABLISHED CONTEXT RULE:
   If user refers to something already established in conversation:
   - Example: "what's my name?" (already provided)
   THEN choose: general (this is contextual knowledge, not new query)

6. UNCLEAR/INVALID INPUT RULE:
   If query is unintelligible, random text, or can't be understood:
   THEN choose: general

7. VISUAL-HEAVY QUERIES:
   If query emphasizes visual representation as primary need:
   - Keywords: draw, show, visualize, diagram, flowchart, architecture
   - Check if explanation is ALSO needed
   - If yes → research_with_diagram
   - If no → diagram

8. SEARCH-REQUIRING QUERIES:
   If query needs current information, external data, or deep knowledge:
   - Examples: "latest trends in AI", "best practices for", "how does X technology work"
   THEN choose: research

========================
CLASSIFICATION EXAMPLES:
========================

DIAGRAM INTENT:
- draw rag pipeline → diagram
- show kafka architecture → diagram
- visualize microservices workflow → diagram
- create flowchart of payment system → diagram
- sketch an ER diagram for users table → diagram
- illustrate the oauth flow → diagram

RESEARCH_WITH_DIAGRAM INTENT:
- explain rag pipeline with diagram → research_with_diagram
- explain kafka visually → research_with_diagram
- show and describe kubernetes architecture → research_with_diagram
- draw a diagram and explain how microservices work → research_with_diagram

RESEARCH INTENT:
- explain rag pipeline → research
- what is microservices architecture? → research
- how does oauth work? → research
- tell me about kubernetes → research
- explain the differences between sql and nosql → research

QUESTION_ANSWER INTENT:
- what is REST API? → question_answer
- define JSON → question_answer
- what's a microservice? → question_answer
- what does CRUD mean? → question_answer

CALCULATION INTENT:
- what is 5 + 3? → calculation
- solve for x in 2x + 5 = 15 → calculation
- calculate compound interest for $1000 at 5% → calculation
- integrate x^2 from 0 to 1 → calculation
- what's the square root of 144? → calculation

CODING INTENT:
- write a python function for factorial → coding
- debug this javascript code → coding
- how do I implement binary search? → coding
- create a rest api endpoint → coding

HOW_TO INTENT:
- how do I deploy to AWS? → how_to
- steps to set up docker → how_to
- tutorial on react hooks → how_to
- guide for setting up CI/CD pipeline → how_to

TRANSFORMATION INTENT:
- convert this json to xml → transformation
- transform this csv to a table → transformation
- rewrite this sql query more efficiently → transformation
- convert this pseudocode to python → transformation

RECOMMENDATION INTENT:
- recommend a javascript framework → recommendation
- what's the best practice for error handling? → recommendation
- suggest a database for this use case → recommendation
- what are the top tools for DevOps? → recommendation

PDF INTENT:
- create a pdf report from this data → pdf
- generate pdf from this template → pdf
- download as pdf → pdf
- save this as a pdf file → pdf

GENERAL INTENT:
- hi → general
- hello, how are you? → general
- xyx → general
- random text that can't be understood → general
- what's my name? (already established) → general

========================
OUTPUT FORMAT:
========================

Return ONLY the intent name.
No JSON.
No explanation.
No extra words.
No punctuation.

Examples of valid output:
diagram
research
coding
calculation
how_to
general

Examples of INVALID output:
{{"intent": "diagram"}}
The intent is: diagram
diagram.
diagram with explanation
""",
        ),
        ("human", "{query}"),
    ]
)

# ---------------- Node Function ----------------
def detect_intent_node(state):
    """
    Detects user intent from the query using LLM + keyword-based fallback.

    Args:
        state: Graph state containing 'prompt' (current query) and optionally 'messages' (history)

    Returns:
        Dict with 'intent' key containing the detected intent
    """
    query = state.get("prompt", "").strip()
    messages = state.get("messages", [])

    if not query:
        return {"intent": "general"}

    # Build conversation context from history
    history_context = ""
    if messages:
        recent = messages[-4:]  # Last 2 exchanges for context
        history_context = "\n".join(
            f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}"
            for m in recent
        )

    # Combine history + current query for better context
    full_context = (
        f"Conversation so far:\n{history_context}\n\nLatest user message: {query}"
        if history_context
        else query
    )

    try:
        # Try LLM-based intent detection first
        chain = intent_template | model | StrOutputParser()
        intent = chain.invoke({"query": full_context}).strip().lower()

        # Validate intent is in allowed list
        allowed_intents = {
            "research",
            "coding",
            "research_with_diagram",
            "diagram",
            "calculation",
            "transformation",
            "recommendation",
            "how_to",
            "general",
            "question_answer",
            "pdf",
        }

        if intent in allowed_intents:
            print(f"✓ LLM Detected intent: {intent}")
            return {"intent": intent}
        else:
            print(f"⚠ LLM returned invalid intent: {intent}. Using keyword fallback.")

    except Exception as e:
        print(f"⚠ LLM intent detection failed: {str(e)}. Using keyword fallback.")

    # ============ KEYWORD-BASED FALLBACK ============
    query_lower = query.lower()

    # Define keyword sets for each intent
    intent_keywords = {
        "pdf": ["generate pdf", "create pdf", "make pdf", "download pdf", "save as pdf", "export to pdf", ".pdf"],
        "calculation": ["+", "-", "*", "/", "%", "^", "calculate", "solve for", "compute", "math", "equation", "integral", "derivative", "sqrt", "sin", "cos", "log"],
        "coding": ["write", "code", "function", "script", "implement", "debug", "fix", "program", "def ", "class ", "import", "algorithm", "python", "javascript", "java"],
        "how_to": ["how do", "how to", "steps to", "tutorial", "guide", "walkthrough", "instruction", "procedure", "step by step"],
        "diagram": ["draw", "show", "visualize", "diagram", "sketch", "render", "plot", "illustrate", "architecture", "workflow", "flowchart", "pipeline", "schema", "erd", "state machine", "network diagram"],
        "recommendation": ["recommend", "suggestion", "best practice", "suggest", "what's the best", "should i use", "which is better", "top tools", "choose"],
        "transformation": ["convert", "transform", "rewrite", "change", "adapt", "format", "restructure", "migrate"],
        "research": ["explain", "tell me about", "describe", "what is", "how does", "understand", "learn about", "why"],
    }

    # Check for visualization + explanation combo (research_with_diagram)
    if any(kw in query_lower for kw in intent_keywords["diagram"]):
        explanation_keywords = ["explain", "describe", "and explain", "with explanation", "visually"]
        if any(kw in query_lower for kw in explanation_keywords):
            print(f"✓ Keyword Detected intent: research_with_diagram")
            return {"intent": "research_with_diagram"}

    # Check each intent's keywords
    for intent, keywords in intent_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            print(f"✓ Keyword Detected intent: {intent}")
            return {"intent": intent}

    # Check for simple question-answer patterns
    question_patterns = ["what is", "who is", "when did", "where is", "define", "what does", "what's a"]
    if any(pattern in query_lower for pattern in question_patterns):
        # Make sure it's not a visualization question
        if not any(kw in query_lower for kw in intent_keywords["diagram"]):
            print(f"✓ Keyword Detected intent: question_answer")
            return {"intent": "question_answer"}

    # Check for greetings
    greetings = ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "how are you", "what's up"]
    if any(greeting in query_lower for greeting in greetings):
        print(f"✓ Keyword Detected intent: general")
        return {"intent": "general"}

    # Default to general if nothing matches
    print(f"✓ Keyword Detected intent: general (default)")
    return {"intent": "general"}
