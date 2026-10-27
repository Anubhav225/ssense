import os
import sys
import re
import base64
import subprocess
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
INPUT_MD = SCRIPT_DIR / "ssense_paper.md"
OUTPUT_HTML = SCRIPT_DIR / "ssense_paper_rendered.html"
OUTPUT_PDF = SCRIPT_DIR / "ssense_paper.pdf"

print(f"Reading markdown from: {INPUT_MD}")
with open(INPUT_MD, "r", encoding="utf-8") as f:
    raw_md = f.read()

# Preprocess markdown to protect LaTeX math before markdown parsing
# Markdown parsers often corrupt underscores, asterisks, and backslashes inside LaTeX math ($...$ and $$...$$)
math_blocks = []
def save_display_math(match):
    idx = len(math_blocks)
    math_blocks.append(match.group(0))
    return f"<!--MATH_DISPLAY_{idx}-->"

def save_inline_math(match):
    idx = len(math_blocks)
    math_blocks.append(match.group(0))
    return f"<!--MATH_INLINE_{idx}-->"

# Protect display math ($$...$$)
processed_md = re.sub(r'\$\$(.*?)\$\$', save_display_math, raw_md, flags=re.DOTALL)
# Protect inline math ($...$) - not matching currency $250
processed_md = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', save_inline_math, processed_md)

# Convert Markdown to HTML using markdown_it
import markdown_it
md = markdown_it.MarkdownIt().enable('table')
html_body = md.render(processed_md)

# Restore protected math blocks
for idx, math_content in enumerate(math_blocks):
    html_body = html_body.replace(f"&lt;!--MATH_DISPLAY_{idx}--&gt;", math_content)
    html_body = html_body.replace(f"<!--MATH_DISPLAY_{idx}-->", math_content)
    html_body = html_body.replace(f"&lt;!--MATH_INLINE_{idx}--&gt;", math_content)
    html_body = html_body.replace(f"<!--MATH_INLINE_{idx}-->", math_content)

# Resolve image paths: embed images as base64 data URIs so Edge headless renders them instantly offline
def embed_image(match):
    src = match.group(1)
    # Check if image exists relative to docs/paper/
    img_path = SCRIPT_DIR / src
    if not img_path.exists():
        # Check relative to repo root
        img_path = REPO_ROOT / src
    if img_path.exists():
        ext = img_path.suffix.lower().replace(".", "")
        if ext == "jpg": ext = "jpeg"
        with open(img_path, "rb") as img_file:
            b64_data = base64.b64encode(img_file.read()).decode("utf-8")
        return f'<img src="data:image/{ext};base64,{b64_data}" class="paper-figure"'
    return match.group(0)

html_body = re.sub(r'<img\s+src="([^"]+)"', embed_image, html_body)

# Wrap tables with a container for clean IEEE styling
html_body = re.sub(r'<table>', '<div class="table-container"><table>', html_body)
html_body = re.sub(r'</table>', '</table></div>', html_body)

# Assemble IEEE Transactions HTML Document
html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Ssense: A Domain-Adapted Legal Language Model for Verifiable Statutory Compliance Auditing under India's DPDP Act, 2023</title>

<!-- MathJax Configuration -->
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$', '$']],
    displayMath: [['$$', '$$']],
    processEscapes: true
  }},
  svg: {{
    fontCache: 'global'
  }},
  startup: {{
    ready: () => {{
      MathJax.startup.defaultReady();
      window.__mathjax_done = true;
    }}
  }}
}};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>

<style>
@page {{
  size: A4;
  margin: 20mm 15mm 20mm 15mm;
  @bottom-right {{
    content: counter(page);
    font-family: "Times New Roman", Times, serif;
    font-size: 9pt;
  }}
}}

body {{
  font-family: "Times New Roman", Times, "Liberation Serif", serif;
  font-size: 10pt;
  line-height: 1.35;
  color: #111;
  background: #fff;
  margin: 0 auto;
  padding: 0;
  max-width: 100%;
  text-align: justify;
  text-justify: inter-word;
}}

/* Title and Authors */
h1:first-of-type {{
  font-size: 18pt;
  font-weight: bold;
  text-align: center;
  margin-top: 0;
  margin-bottom: 12pt;
  line-height: 1.25;
}}

table:first-of-type {{
  margin: 0 auto 16pt auto;
  border: none;
  font-size: 9.5pt;
  text-align: center;
}}
table:first-of-type td {{
  border: none;
  padding: 2pt 12pt;
}}

/* Headings */
h1 {{
  font-size: 12pt;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 18pt;
  margin-bottom: 6pt;
  border-bottom: 1px solid #333;
  padding-bottom: 2pt;
  page-break-after: avoid;
}}

h2 {{
  font-size: 11pt;
  font-weight: bold;
  margin-top: 14pt;
  margin-bottom: 4pt;
  page-break-after: avoid;
}}

h3 {{
  font-size: 10pt;
  font-weight: bold;
  font-style: italic;
  margin-top: 10pt;
  margin-bottom: 4pt;
  page-break-after: avoid;
}}

p {{
  margin-top: 0;
  margin-bottom: 6pt;
  text-indent: 14pt;
}}

p:first-of-type, h1 + p, h2 + p, h3 + p {{
  text-indent: 0;
}}

/* IEEE Table Styling */
.table-container {{
  margin: 12pt auto;
  text-align: center;
  page-break-inside: avoid;
  width: 100%;
  overflow-x: auto;
}}

table {{
  margin: 0 auto;
  border-collapse: collapse;
  font-size: 8.5pt;
  line-height: 1.2;
  border-top: 1.5pt solid #000;
  border-bottom: 1.5pt solid #000;
  width: 100%;
}}

th {{
  border-bottom: 1pt solid #000;
  padding: 4pt 5pt;
  font-weight: bold;
  text-align: center;
  background: #fdfdfd;
}}

td {{
  padding: 3.5pt 5pt;
  border-top: 0.5pt solid #ddd;
  border-bottom: none;
  text-align: left;
}}

tr:hover {{
  background: #f9f9f9;
}}

/* Figures */
img.paper-figure {{
  display: block;
  max-width: 95%;
  height: auto;
  margin: 10pt auto 4pt auto;
  page-break-inside: avoid;
  border: 1px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}

/* Captions */
p:has(strong:first-child) {{
  font-size: 9pt;
  text-align: justify;
  margin-top: 4pt;
  margin-bottom: 12pt;
}}

/* Math */
mjx-container {{
  font-size: 100% !important;
}}

mjx-container[display="true"] {{
  margin: 8pt 0 !important;
}}

/* Code Blocks */
pre {{
  background: #f5f5f5;
  border: 1px solid #ccc;
  padding: 6pt 8pt;
  font-size: 8pt;
  font-family: "Courier New", Courier, monospace;
  overflow-x: auto;
  page-break-inside: avoid;
  margin: 8pt 0;
}}

code {{
  font-family: "Courier New", Courier, monospace;
  font-size: 9pt;
  background: #f0f0f0;
  padding: 1pt 2pt;
  border-radius: 2px;
}}

/* References */
p:has(span.ref-num) {{
  font-size: 8.5pt;
  text-indent: -18pt;
  margin-left: 18pt;
}}

</style>
</head>
<body>
{html_body}
</body>
</html>
"""

print(f"Writing rendered HTML to: {OUTPUT_HTML}")
with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_template)

print("HTML compilation complete. Launching headless browser for PDF generation...")

# Generation via Playwright
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(edge_path):
            browser = p.chromium.launch(executable_path=edge_path, headless=True)
        else:
            browser = p.chromium.launch(headless=True)
            
        page = browser.new_page()
        page.goto(OUTPUT_HTML.as_uri(), wait_until="networkidle", timeout=60000)
        
        # Wait for MathJax typesetting if available
        try:
            page.wait_for_function("() => window.__mathjax_done === true", timeout=15000)
            print("MathJax vector typesetting completed successfully.")
        except Exception as e:
            print(f"Note: MathJax wait timed out ({e}), proceeding with print layout.")
            
        page.pdf(
            path=str(OUTPUT_PDF),
            format="A4",
            print_background=True,
            margin={
                "top": "20mm",
                "bottom": "20mm",
                "left": "15mm",
                "right": "15mm"
            }
        )
        browser.close()
    print(f"PDF generated successfully via Playwright: {OUTPUT_PDF}")
except Exception as e:
    print(f"Playwright PDF generation failed: {e}. Falling back to direct Edge CLI...")
    cmd = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={OUTPUT_PDF}",
        str(OUTPUT_HTML)
    ]
    subprocess.run(cmd, check=True)
    print(f"PDF generated successfully via Edge CLI: {OUTPUT_PDF}")

if OUTPUT_PDF.exists():
    size_mb = OUTPUT_PDF.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: Generated PDF at {OUTPUT_PDF} ({size_mb:.2f} MB)")
    import fitz
    doc = fitz.open(str(OUTPUT_PDF))
    print(f"Total Page Count: {len(doc)} pages.")
    doc.close()
else:
    print("ERROR: PDF file was not created!")
