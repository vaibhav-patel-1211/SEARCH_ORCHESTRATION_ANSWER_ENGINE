"""
coding.py - Secure code generation and execution node.
Flow:
  1. LLM generates Python code based on user's prompt
  2. Code is extracted from markdown response
  3. Each Python block is executed in an E2B sandbox (isolated container)
  4. If execution fails, LLM auto-fixes the code (up to 3 attempts)
  5. Final answer includes execution results (pass/fail + output)

This gives users verified, working code rather than untested suggestions.
"""

import asyncio
import inspect
import re
from e2b_code_interpreter import Sandbox
from config import coding_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from prompts.prompts import coding_system_prompt

MAX_FIX_ATTEMPTS = 3  # max times LLM tries to fix broken code


# ---------------- PRE-PROCESSING ----------------

def strip_think_tags(text: str) -> str:
    """
    Remove <think>...</think> reasoning blocks that some models
    inject into responses. These break code extraction.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------- CODE EXTRACTION ----------------

def extract_all_code_blocks(markdown: str) -> list[dict]:
    """
    Parse markdown and extract all fenced code blocks.
    Returns list of {language, code} dicts.
    Handles edge cases like unclosed blocks (stream cut off mid-response).
    """
    markdown = strip_think_tags(markdown)

    results       = []
    lines         = markdown.split("\n")
    in_block      = False
    current_lang  = ""
    current_lines = []
    fence         = ""

    for line in lines:
        if not in_block:
            # Detect opening fence (``` or ```python etc.)
            match = re.match(r"^(```+)(\w*)\s*$", line)
            if match:
                fence         = match.group(1)
                current_lang  = match.group(2).lower() or "text"
                current_lines = []
                in_block      = True
        else:
            # Detect closing fence (must match exactly)
            if line.rstrip() == fence:
                if current_lines:
                    results.append({
                        "language": current_lang,
                        "code": "\n".join(current_lines).strip()
                    })
                in_block      = False
                current_lang  = ""
                current_lines = []
                fence         = ""
            else:
                current_lines.append(line)

    # Handle truncated/unclosed block (stream cut off mid-response)
    if in_block and current_lines:
        print("⚠ Unclosed code block detected (stream truncated) — capturing anyway.")
        results.append({
            "language": current_lang,
            "code": "\n".join(current_lines).strip()
        })

    return results


def extract_first_python_block(markdown: str) -> str | None:
    """Return the first Python code block found, or None."""
    blocks = extract_all_code_blocks(markdown)
    for b in blocks:
        if b["language"] in ("python", "py"):
            return b["code"]
    return None




# ---------------- SANDBOX EXECUTION ----------------

def run_in_sandbox(code: str, sandbox=None) -> dict:
    """
    Execute Python code in an E2B cloud sandbox (isolated container).
    This is safe - user code can't affect our server.
    Returns {success: bool, output: str, error: str|None}
    """
    try:
        # Auto-install any pip packages referenced in the code
        pip_patterns = re.findall(
            r'(?:!pip|pip|subprocess\.run\(\[.?pip.?,\s*.?install.?,\s*)install\s+([\w\-]+)',
            code
        )
        if pip_patterns and sandbox:
            for pkg in pip_patterns:
                pkg = pkg.strip().strip('"').strip("'")
                if pkg:
                    print(f"   📦 Installing package: {pkg}...")
                    sandbox.commands.run(f"pip install {pkg}")

        if sandbox:
            result = sandbox.run_code(code, timeout=60)
            return format_sandbox_result(result)
        else:
            with Sandbox.create() as sbx:
                result = sbx.run_code(code, timeout=60)
                return format_sandbox_result(result)

    except Exception as e:
        return {
            "success": False,
            "output":  "",
            "error":   str(e)
        }

def format_sandbox_result(result) -> dict:
    """Convert E2B sandbox result into our standard format."""
    stdout = "".join(result.logs.stdout or [])
    stderr = "".join(result.logs.stderr or [])

    if result.error:
        return {
            "success": False,
            "output":  stdout,
            "error": (
                f"{result.error.name}: {result.error.value}\n"
                f"{result.error.traceback or ''}"
            )
        }

    output = stdout
    if stderr:
        output += f"\n⚠ Stderr:\n{stderr}"

    return {
        "success": True,
        "output":  output.strip() or "✅ Ran successfully (no output)",
        "error":   None
    }


# ---------------- LLM CODE FIXER ----------------

def fix_code_with_llm(original_prompt: str, broken_code: str, error: str) -> str:
    """
    Self-healing: sends broken code + error traceback to LLM,
    asks it to fix the bugs. Returns corrected code.
    """
    fix_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an expert Python debugger.
You will receive broken code and the exact error it produced when executed.
Your job:
- Fix ALL bugs in the code.
- Return ONLY the corrected code inside a single ```python block.
- The code must be complete and runnable as-is.
- Do NOT add explanations, comments outside the code, or any text outside the code block.
- Do NOT wrap your answer in <think> tags."""
        ),
        (
            "human",
            """Original task: {original_prompt}

Broken code:
```python
{broken_code}
```

Exact error from execution:
{error}

Return the fixed code now:"""
        )
    ])

    chain    = fix_prompt | coding_model | StrOutputParser()
    response = chain.invoke({
        "original_prompt": original_prompt,
        "broken_code":     broken_code,
        "error":           error
    })

    response = strip_think_tags(response)
    fixed    = extract_first_python_block(response)
    return fixed if fixed else broken_code   # fallback: return original if parse fails


# ---------------- MAIN NODE ----------------

def _verify_and_annotate_code(
    user_prompt: str,
    clean_answer: str,
    python_blocks: list[dict],
) -> str:
    """
    Takes all Python blocks from the LLM response, executes each in sandbox,
    auto-fixes failures, and appends execution results to the answer.
    """
    execution_results = []

    final_answer = clean_answer

    try:
        # Create one sandbox session for all blocks (preserves state between them)
        with Sandbox.create() as sbx:
            for block_num, block in enumerate(python_blocks, 1):
                code = block["code"]
                attempt = 0
                last_error = None
                fixed = False

                # Try-fix loop: execute, if fails -> fix -> retry
                while attempt < MAX_FIX_ATTEMPTS:
                    attempt += 1
                    result = run_in_sandbox(code, sandbox=sbx)

                    if result["success"]:
                        execution_results.append(
                            {
                                "block_num": block_num,
                                "original": block["code"],
                                "final_code": code,
                                "output": result["output"],
                                "attempts": attempt,
                                "fixed": fixed,
                                "status": "success",
                            }
                        )
                        break

                    last_error = result["error"]
                    if attempt < MAX_FIX_ATTEMPTS:
                        code = fix_code_with_llm(user_prompt, code, last_error)
                        fixed = True
                else:
                    # All attempts exhausted - mark as failed
                    execution_results.append(
                        {
                            "block_num": block_num,
                            "original": block["code"],
                            "final_code": code,
                            "output": "",
                            "attempts": attempt,
                            "fixed": fixed,
                            "status": "failed",
                            "error": last_error,
                        }
                    )
    except Exception as exc:
        if not execution_results:
            return f"{clean_answer}\n\nExecution verification failed: {exc}"

    # Replace broken code blocks with fixed versions in the answer
    for res in execution_results:
        if res["fixed"] and res["status"] == "success":
            old_block = f"```python\n{res['original']}\n```"
            new_block = f"```python\n{res['final_code']}\n```"
            if old_block in final_answer:
                final_answer = final_answer.replace(old_block, new_block, 1)

    # Append execution results section at the end
    exec_section = "\n\n---\n## Execution Results\n\n"

    for res in execution_results:
        status_icon = "PASS" if res["status"] == "success" else "FAIL"
        attempts = res["attempts"]
        fix_note = (
            f" *(auto-fixed in {attempts} attempt{'s' if attempts > 1 else ''})*"
            if res["fixed"] else ""
        )

        exec_section += f"### {status_icon} Code Block {res['block_num']}{fix_note}\n\n"

        if res["status"] == "success":
            exec_section += f"**Output:**\n```\n{res['output']}\n```\n\n"
        else:
            exec_section += f"**Failed.**\n\n**Last Error:**\n```\n{res.get('error', 'Unknown error')}\n```\n\n"

    final_answer += exec_section
    return final_answer


async def coding_node(state, config=None):
    """
    Graph node entry point for coding queries.
    1. Streams LLM response (code + explanation)
    2. Extracts Python blocks
    3. Verifies each block in E2B sandbox
    4. Returns final answer with execution results
    """
    user_prompt = state["prompt"]
    memory_context = (state.get("memory_context") or "").strip()
    skill_context = (state.get("skill_context") or "").strip()

    prompt = ChatPromptTemplate.from_messages([
        ("system", coding_system_prompt),
        (
            "human",
            """Original Prompt: {prompt}

Private User Memory Context (for personalization only):
{memory_context}

Active Skill Instructions (apply when relevant):
{skill_context}

Write a complete, working solution with inline comments.
Explain each section clearly after the code.
Mention alternative approaches or libraries if relevant."""
        ),
    ])

    formatted = prompt.format_messages(
        prompt=user_prompt,
        memory_context=memory_context or "No user memory available.",
        skill_context=skill_context or "No active skills.",
    )
    chain = coding_model | StrOutputParser()
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    token_callback = configurable.get("token_callback")

    # Stream tokens to frontend in real-time
    llm_answer = ""
    async for token in chain.astream(formatted):
        if not token:
            continue
        llm_answer += token
        if token_callback:
            callback_result = token_callback(token)
            if inspect.isawaitable(callback_result):
                await callback_result

    clean_answer = strip_think_tags(llm_answer)
    all_blocks = extract_all_code_blocks(clean_answer)
    python_blocks = [b for b in all_blocks if b["language"] in ("python", "py")]

    # If no Python code found, just return the explanation as-is
    if not python_blocks:
        return {"final_answer": clean_answer}

    # Run verification in a thread (sandbox calls are blocking)
    verified_answer = await asyncio.to_thread(
        _verify_and_annotate_code,
        user_prompt,
        clean_answer,
        python_blocks,
    )
    return {"final_answer": verified_answer}
