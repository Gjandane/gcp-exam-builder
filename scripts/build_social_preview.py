"""Render the GitHub social preview. Spec 0001, 0 Showcase.

Takes one frame of docs/assets/hero-review.gif (Demo bank, graded question),
puts it beside the README title and tagline in a small HTML page, renders
that with Playwright and writes docs/assets/social-preview.png, 1280x640,
under 1 MB. Reads committed files only.

Needs Playwright's Chromium (`playwright install chromium`). Run:

    python scripts/build_social_preview.py
"""

import base64
import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
GIF = ROOT / "docs" / "assets" / "hero-review.gif"
OUT = ROOT / "docs" / "assets" / "social-preview.png"
WIDTH, HEIGHT = 1280, 640
MAX_BYTES = 1024 * 1024

TITLE = "GCP Exam Builder"
TAGLINE = (
    "Build your own Google Cloud certification question bank with Claude Code, "
    "then drill it in a free Google Sheets exam simulator."
)
BADGES = ["Claude Code skill", "Google Apps Script"]

# Frame 40 of the hero GIF: question graded, every explanation open, top of the card visible.
FRAME = 40
# Keep the frame from the filter row down to the "Correct!" box.
CROP_BOTTOM = 810

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ width: {w}px; height: {h}px; overflow: hidden;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    background: linear-gradient(135deg, #0b1f3a 0%, #123a6b 100%); color: #fff;
    display: flex; align-items: center; padding: 0 56px 0 72px; gap: 56px; }}
  .text {{ flex: 1; }}
  .badges {{ display: flex; gap: 12px; margin-bottom: 28px; }}
  .badge {{ font-size: 22px; font-weight: 600; padding: 6px 16px; border-radius: 999px;
    background: rgba(255,255,255,.14); color: #cfe0ff; }}
  h1 {{ font-size: 84px; line-height: 1.02; font-weight: 800; letter-spacing: -1px; margin-bottom: 28px; }}
  p {{ font-size: 37px; line-height: 1.3; color: #dbe7fb; }}
  .shot {{ flex: none; height: 560px; border-radius: 16px; overflow: hidden;
    box-shadow: 0 24px 60px rgba(0,0,0,.45); border: 1px solid rgba(255,255,255,.25); }}
  .shot img {{ display: block; height: 100%; }}
</style></head><body>
  <div class="text">
    <div class="badges">{badges}</div>
    <h1>{title}</h1>
    <p>{tagline}</p>
  </div>
  <div class="shot"><img src="data:image/png;base64,{img}"></div>
</body></html>"""


def frame_png():
    gif = Image.open(GIF)
    gif.seek(min(FRAME, gif.n_frames - 1))
    frame = gif.convert("RGB")
    frame = frame.crop((0, 0, frame.width, min(CROP_BOTTOM, frame.height)))
    buf = io.BytesIO()
    frame.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    html = HTML.format(
        w=WIDTH,
        h=HEIGHT,
        badges="".join(f'<span class="badge">{b}</span>' for b in BADGES),
        title=TITLE,
        tagline=TAGLINE,
        img=frame_png(),
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        page.set_content(html)
        page.wait_for_load_state("load")
        shot = page.screenshot(clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT})
        browser.close()

    img = Image.open(io.BytesIO(shot)).convert("RGB")
    img.save(OUT, "PNG", optimize=True)
    if OUT.stat().st_size > MAX_BYTES:
        img.quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(OUT, "PNG", optimize=True)

    size = OUT.stat().st_size
    with Image.open(OUT) as check:
        dims = check.size
    print(f"{OUT.relative_to(ROOT)}: {dims[0]}x{dims[1]}, {size} bytes")
    if dims != (WIDTH, HEIGHT) or size > MAX_BYTES:
        sys.exit("social preview is the wrong size or over 1 MB")


if __name__ == "__main__":
    main()
