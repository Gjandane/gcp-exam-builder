"""Render the real `export` summary as a terminal-style PNG. Spec 0001, 0 Showcase.

Runs the skill's export on the real bank, masks question-site names and local
paths in the text, then renders it with Playwright as a dark terminal window
into docs/assets/export-summary.png. Masking happens on the text, before
rendering. Run from the main checkout (the bank in exam-bank/ is gitignored):

    python scripts/render_export_summary.py [exam]

The exam defaults to pmle. Needs `playwright install chromium`.
"""

import html
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets" / "export-summary.png"
EB = ".claude/skills/exam-bank/scripts/eb.py"
WIDTH = 900

# A user or absolute path: Windows drive paths, POSIX home and system paths, ~.
PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|~[\\/]|/(?:home|Users|root|tmp|mnt|var|opt)/)[^\s\"'<>|]*")


def source_names(config: dict) -> list[str]:
    """Every configured source name, curated sites then llm sources."""
    return [s["name"] for s in config.get("curated_sites", []) + config.get("llm_sources", [])]


def mask(text: str, names: list[str], root: Path) -> str:
    """Replace each source name with source-N and each local path with a repo-relative one."""
    for index, name in sorted(enumerate(names, 1), key=lambda item: -len(item[1])):
        text = re.sub(re.escape(name), f"source-{index}", text, flags=re.IGNORECASE)
    for form in {str(root), root.as_posix()}:
        text = re.sub(re.escape(form) + r"[\\/]?", "", text, flags=re.IGNORECASE)
    return PATH_RE.sub(lambda m: ".../" + re.split(r"[\\/]", m[0].rstrip("\\/"))[-1], text)


def run_export(exam: str) -> str:
    result = subprocess.run([sys.executable, EB, "export", exam], cwd=ROOT,
                            capture_output=True, encoding="utf-8")
    if result.returncode != 0:
        # The refusal names row IDs only; still, print no more than its first line.
        reason = (result.stderr or result.stdout).strip().splitlines()
        sys.exit(f"export failed, no image written: {reason[0] if reason else result.returncode}")
    return result.stdout


def page(exam: str, text: str) -> str:
    body = html.escape(text.rstrip("\n"))
    return f"""<!doctype html><meta charset="utf-8"><style>
body {{ margin: 0; background: #ffffff; }}
.win {{ width: {WIDTH - 32}px; margin: 16px; border-radius: 10px; overflow: hidden;
  background: #1e1e1e; box-shadow: 0 6px 18px rgba(0,0,0,.25); }}
.bar {{ height: 30px; background: #323232; display: flex; align-items: center; padding: 0 12px; gap: 8px; }}
.dot {{ width: 12px; height: 12px; border-radius: 50%; }}
pre {{ margin: 0; padding: 16px 20px 20px; color: #d4d4d4; white-space: pre-wrap;
  font: 15px/1.5 Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace; }}
.prompt {{ color: #6a9955; }} .cmd {{ color: #e8e8e8; font-weight: bold; }}
</style><div class="win"><div class="bar">
<span class="dot" style="background:#ff5f57"></span><span class="dot" style="background:#febc2e"></span>
<span class="dot" style="background:#28c840"></span></div>
<pre><span class="prompt">&gt;</span> <span class="cmd">/exam-bank {html.escape(exam)} export</span>

{body}</pre></div>"""


def render(exam: str, text: str, out: Path) -> None:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        tab = browser.new_page(viewport={"width": WIDTH, "height": 400}, device_scale_factor=1)
        tab.set_content(page(exam, text))
        tab.locator("body").screenshot(path=str(out), animations="disabled", caret="hide")
        browser.close()
    Image.open(out).convert("RGB").save(out, optimize=True)


def main() -> None:
    exam = sys.argv[1] if len(sys.argv) > 1 else "pmle"
    config_path = ROOT / "exam-bank" / "config" / "exams" / f"{exam}.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    text = mask(run_export(exam), source_names(config), ROOT)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    render(exam, text, OUT)
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
