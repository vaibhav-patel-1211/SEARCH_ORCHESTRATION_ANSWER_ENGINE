import re

from langchain_core.output_parsers import NumberedListOutputParser
from langchain_core.prompts import PromptTemplate
from config import model
from prompts import prompts

# ---------------- PDF TOPIC CLEANER ----------------

PDF_NOISE_PATTERN = re.compile(
    r"\b(pdf|generate|create|make|download|export|give me|that include|"
    r"that includes|including|a |an |the |about|on|for)\b",
    flags=re.IGNORECASE
)

def extract_topic_from_pdf_prompt(prompt: str) -> str:
    """
    Strips PDF-related noise words to extract the real search topic.

    Examples:
        'give me pdf that include what is machine learning'
            → 'what is machine learning'
        'generate pdf about quantum computing'
            → 'quantum computing'
        'create a pdf on neural networks'
            → 'neural networks'
    """
    cleaned = PDF_NOISE_PATTERN.sub(" ", prompt)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()  # collapse extra spaces
    result  = cleaned if cleaned else prompt          # fallback to original
    print(f"📄 PDF topic extracted: '{prompt}' → '{result}'")
    return result


# ---------------- TEMPLATE SELECTOR ----------------

def get_template_for_intent(intent: str) -> str:
    """Return the correct prompt template based on intent."""
    template_map = {
        "research":              prompts.research_template,
        "pdf":                   prompts.research_template,   # PDF uses research template
        "coding":                prompts.research_template,
        "calculation":           prompts.calculation_template,
        "recommendation":        prompts.recommendation_template,
        "how_to":                prompts.howto_template,
        "diagram":               prompts.diagram_template,
        "research_with_diagram": prompts.research_with_diagram_template,
        "question_answer":       prompts.research_template,
        "transformation":        prompts.research_template,
    }
    return template_map.get(intent, prompts.general_template)


# ---------------- NODE ----------------

def generate_sub_queries_node(state):
    """
    Takes a user query and returns a list of intelligently decomposed sub-queries.

    Special handling for 'pdf' intent:
        Strips PDF-related noise words first so the optimizer searches
        for the actual topic (e.g. 'machine learning') not the format ('pdf').
    """
    intent = state.get("intent", "general")
    prompt = state["prompt"]

    # For PDF intent, clean the prompt to extract the real search topic
    if intent == "pdf":
        prompt = extract_topic_from_pdf_prompt(prompt)

    # --- 1. Output Parser ---
    output_parser        = NumberedListOutputParser()
    format_instructions  = output_parser.get_format_instructions()

    # --- 2. Prompt Template ---
    template = get_template_for_intent(intent)

    prompt_template = PromptTemplate(
        template=template,
        input_variables=["query"],
        partial_variables={"format_instructions": format_instructions}
    )

    # --- 3. Chain ---
    chain = prompt_template | model | output_parser

    # --- 4. Invoke with cleaned prompt ---
    sub_queries = chain.invoke({"query": prompt})

    print(f"✅ Generated {len(sub_queries)} sub-queries for intent '{intent}':")
    for i, q in enumerate(sub_queries, 1):
        print(f"   {i}. {q}")

    return {"sub_queries": sub_queries}
