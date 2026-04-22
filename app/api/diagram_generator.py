import asyncio
import os
from playwright.async_api import async_playwright  #type:ignore
from langchain.tools import tool #type:ignore

async def generate_diagram(mermaid_code, output_path = 'diagram.png'):
    """
    Generates a cropped PNG image from Mermaid.js markdown syntax using a headless browser.

    This function uses Playwright to render a temporary HTML page containing the Mermaid code,
    waits for the JavaScript library to render the SVG, and takes a precisely cropped
    screenshot of the resulting diagram.

    Args:
        mermaid_code (str): A valid Mermaid.js diagram string (e.g., 'graph TD...').
        output_path (str): The local file path where the .png image should be saved.

    Returns:
        None: Saves the file to the specified output_path.

    Raises:
        playwright._impl._errors.TimeoutError: If the diagram takes longer than 5s to render.
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    async with async_playwright() as p:
        # 1. Launch browser (headless=True is default)
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # 2. Updated HTML with a "ready" check
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

        # 3. FIX: Change selector to ".mermaid svg" (with a space)
        # Or wait for the attribute 'data-processed' which mermaid adds
        try:
            # We wait for the SVG element to appear inside the mermaid div
            await page.wait_for_selector(".mermaid svg", timeout=5000)

            # 4. FIX: Define 'element' properly before taking screenshot
            element = await page.query_selector(".mermaid")
            await element.screenshot(path=output_path) #type:ignore
        except Exception as e:
            raise RuntimeError(f"Error rendering diagram: {e}") from e
        finally:
            # 5. FIX: Correct spelling of 'browser'
            await browser.close()

diagram_markdown = """
graph TD
    A[User Query] --> B{Search Engine}
    B -->|Code| C[Frontend Code Block]
    B -->|Table| D[Frontend Table]
"""


tools = [generate_diagram]
