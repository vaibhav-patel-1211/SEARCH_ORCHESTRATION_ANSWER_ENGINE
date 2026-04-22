from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from regex import template
from config import model

def _generate_tags(user_query) :
    """
    Takes a user query and returns a list of tags.
    """

    # outputparser
    output_parser =CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()

    # prompt template
    template = """
You are an AI system that extracts ONLY the main high-level topic tags from a user query.

Rules:
- Generate between 2 -3 tag only
- Focus on core concepts, not details or subcomponents
- Convert to lowercase
- Use snake_case format
- Return tags separated by commas only
- Do not explain anything

Good examples:

User: what is machine learning?
Output: machine_learning, artificial_intelligence

User: Explain CNN and image classification
Output: convolutional_neural_networks, image_classification

User: How does vector database work in RAG?
Output: vector_database, retrieval_augmented_generation, semantic_search

User: What is Kafka used for in microservices?
Output: apache_kafka, microservices, event_driven_architecture, message_broker, event_streaming

Now generate main topic tags for:

User: {user_query}
Output:
"""


    prompt = PromptTemplate(
      template=template,
      input_variables=["user_query"],
      partial_variables={"format_instructions": format_instructions}
   )

    # chain
    chain = prompt | model |output_parser

    tags = chain.invoke({"user_query" : user_query})

    return tags



def generate_tags_node(state):
    queries = state['sub_queries']

    all_tags = []

    for q in queries:
        tags = _generate_tags(q)   # FIXED
        all_tags.extend(tags)      # flatten

    # Optional: remove duplicates
    unique_tags = list(set(all_tags))

    return {"tags": unique_tags}




  # ------------Test---------------------------
if __name__ == '__main__' :
  user_query = "How does vector search improve RAG?"

