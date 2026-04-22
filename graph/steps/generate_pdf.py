import os
import uuid
import re
from e2b_code_interpreter import Sandbox
from config import coding_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from prompts.prompts import pdf_system_prompt

OUTPUT_DIR = "static/reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_python_code(text: str) -> str:
    """
    Robust extraction of Python code from LLM response.
    1. Look for ```python ... ```
    2. Look for ``` ... ```
    3. Fallback to cleaning the whole string if it looks like code.
    """
    # 1. Standard markdown extraction
    match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 2. Any backticks
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 3. No backticks but contains code-like markers
    lines = text.splitlines()
    clean_lines = []
    found_start = False
    for line in lines:
        # Start capturing from first import/from/def
        if not found_start and (line.strip().startswith("import ") or line.strip().startswith("from ")):
            found_start = True
        
        if found_start:
            # Stop if we hit conversational filler after a block of code
            # (Crude heuristic: more than 2 empty lines or sentences without code patterns)
            clean_lines.append(line)
            
    if clean_lines:
        return "\n".join(clean_lines).strip()

    return text.strip()

def generate_pdf_node(state):
    """
    Agentic PDF Generation with Self-Healing:
    1. Writes content to 'content.txt' in the sandbox.
    2. Installs reportlab.
    3. LLM writes a script (with a strict import skeleton).
    4. If it fails, the LLM is asked to fix the specific error.
    """
    print("\n🎨 Agent is designing and coding your PDF...")
    
    prompt = state.get("prompt", "")
    final_answer = state.get("final_answer", "")
    
    if not final_answer:
        print("⚠️ No final_answer found to generate PDF. Using prompt as fallback.")
        final_answer = f"Research Report for: {prompt}\n\n(No detailed content was generated)"

    # Replace placeholder in system prompt
    formatted_system_prompt = pdf_system_prompt.format(topic=prompt)

    file_id = uuid.uuid4().hex[:10]
    local_filename = f"report_{file_id}.pdf"
    local_filepath = os.path.join(OUTPUT_DIR, local_filename)
    
    try:
        with Sandbox.create() as sbx:
            print(f"📦 Preparing sandbox (Content size: {len(final_answer)} characters)...")
            sbx.commands.run("pip install reportlab")
            sbx.files.write("content.txt", final_answer)
            
            attempt = 0
            max_attempts = 2
            last_error = None
            code_to_run = None

            while attempt < max_attempts:
                attempt += 1
                
                if attempt == 1:
                    print("🚀 Generating PDF script...")
                    chain = coding_model | StrOutputParser()
                    code_to_run = extract_python_code(
                        chain.invoke(
                            [
                                SystemMessage(content=formatted_system_prompt),
                                HumanMessage(
                                    content=(
                                        f"Create the professional PDF report for: {prompt}. "
                                        "Ensure ALL content from content.txt is included."
                                    )
                                ),
                            ]
                        )
                    )
                else:
                    print(f"🔧 Fixing PDF script (Attempt {attempt})...")
                    fix_chain = coding_model | StrOutputParser()
                    code_to_run = extract_python_code(
                        fix_chain.invoke(
                            [
                                SystemMessage(
                                    content="You are a debugger. Fix the provided code based on the error. Return ONLY code."
                                ),
                                HumanMessage(content=f"Error: {last_error}\n\nCode:\n{code_to_run}"),
                            ]
                        )
                    )

                execution = sbx.run_code(code_to_run)
                
                if not execution.error:
                    # Check if file exists before trying to read
                    try:
                        print("📥 Downloading PDF...")
                        pdf_bytes = sbx.files.read("generated_report.pdf", format="bytes")
                        with open(local_filepath, "wb") as f:
                            f.write(pdf_bytes)
                        print(f"✅ Agentically generated PDF: {local_filepath}")
                        return {"pdf_path": local_filepath, "pdf_filename": local_filename}
                    except Exception as e:
                        last_error = f"Execution succeeded but 'generated_report.pdf' was not found. Ensure you call doc.build('generated_report.pdf'). Error: {str(e)}"
                        print(f"⚠️ {last_error}")
                else:
                    last_error = execution.error
                    print(f"❌ Attempt {attempt} failed: {str(last_error).splitlines()[0]}")

        return {"pdf_path": None, "pdf_filename": None}
        
    except Exception as e:
        print(f"❌ Error during agentic PDF generation: {str(e)}")
        return {"pdf_path": None, "pdf_filename": None}
