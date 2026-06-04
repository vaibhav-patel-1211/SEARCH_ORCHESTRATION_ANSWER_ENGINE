import asyncio
import os
import sys
import concurrent.futures
from playwright.async_api import async_playwright  #type:ignore
from langchain.tools import tool #type:ignore

async def _generate_diagram_actual(mermaid_code, output_path):
    """The actual async logic for rendering the diagram."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    async with async_playwright() as p:
        # 1. Launch browser (headless=True is default)
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # 2. HTML with mermaid.js
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        </head>
        <body>
            <div id="graph-container">
                <pre class="mermaid">
                    {mermaid_code}
                </pre>
            </div>
            <script>
                // Initialize mermaid
                mermaid.initialize({{ startOnLoad: true }});
            </script>
        </body>
        </html>
        """
        await page.set_content(html_content, wait_until="networkidle")

        try:
            # 3. Wait for the SVG element to appear inside the mermaid div
            await page.wait_for_selector(".mermaid svg", timeout=5000)

            # 4. Take screenshot of the mermaid element
            element = await page.query_selector(".mermaid")
            if element:
                await element.screenshot(path=output_path)
            else:
                raise RuntimeError("Could not find mermaid element after rendering.")
        except Exception as e:
            raise RuntimeError(f"Error rendering diagram: {e}") from e
        finally:
            await browser.close()

def _run_in_new_proactor_loop(mermaid_code, output_path):
    """Helper to run the async diagram generation in a fresh ProactorEventLoop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Force Proactor loop on Windows for this thread
    if sys.platform == 'win32':
        from asyncio import WindowsProactorEventLoop
        loop = WindowsProactorEventLoop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(_generate_diagram_actual(mermaid_code, output_path))
    finally:
        loop.close()

async def generate_diagram(mermaid_code, output_path = 'diagram.png'):
    """
    Generates a cropped PNG image from Mermaid.js markdown syntax using a headless browser.
    
    On Windows, if the current event loop is not a ProactorEventLoop (which happens
    when running via certain uvicorn configurations), it falls back to running
    the generation in a separate thread with its own ProactorEventLoop to avoid
    the NotImplementedError during browser launch.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    is_windows = sys.platform == 'win32'
    is_wrong_loop = is_windows and loop and not isinstance(loop, asyncio.WindowsProactorEventLoop)

    if is_wrong_loop:
        print("🔄 Windows Loop Fix: Running diagram generation in a separate Proactor thread.")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _run_in_new_proactor_loop, mermaid_code, output_path)
    else:
        return await _generate_diagram_actual(mermaid_code, output_path)

diagram_markdown = """
graph TD
    A[User Query] --> B{Search Engine}
    B -->|Code| C[Frontend Code Block]
    B -->|Table| D[Frontend Table]
"""

tools = [generate_diagram]
