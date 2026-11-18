"""Record the README's app images from the local preview. Spec 0002, Visuals, app side.

Starts scripts/preview_app.js (Demo bank, in memory), drives it with Playwright,
and writes into docs/assets/:

    hero-review.gif   Review mode: pick, graded, per-choice explanations
    mock-test.gif     Mock Test: answer, Flag, submit, results
    results.png       results by Section
    history.png       Mock Test history
    report.png        the Report form

Needs node and ffmpeg on PATH, and `playwright install chromium`. Run:

    python scripts/capture_readme.py
"""

import csv
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
DEMO_BANK = ROOT / "docs" / "demo" / "demo-bank.csv"
SIZE = {"width": 720, "height": 860}
GIF_FPS = 8
GIF_MAX_BYTES = 3 * 1024 * 1024
GIF_MAX_SECONDS = 15

# A visible cursor, since recordings do not show the system pointer.
CURSOR_JS = """
(() => {
  const dot = document.createElement('div');
  dot.style.cssText = 'position:fixed;z-index:99999;width:18px;height:18px;margin:-9px 0 0 -9px;'
    + 'border-radius:50%;background:rgba(66,133,244,.45);border:2px solid #4285f4;pointer-events:none;'
    + 'left:-50px;top:-50px;transition:transform .12s';
  document.addEventListener('mousemove', e => { dot.style.left = e.clientX + 'px'; dot.style.top = e.clientY + 'px'; });
  document.addEventListener('mousedown', () => { dot.style.transform = 'scale(.7)'; });
  document.addEventListener('mouseup', () => { dot.style.transform = 'scale(1)'; });
  addEventListener('DOMContentLoaded', () => document.body.appendChild(dot));
})();
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def answer_key():
    """question text -> list of correct choice texts, from the Demo bank."""
    key = {}
    with DEMO_BANK.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            letters = row["answer"].split(",")
            key[row["question"]] = [row["choice_" + l.lower()] for l in letters]
    return key


def wrong_choices(row_choices, correct):
    return [c for c in row_choices if c and c not in correct]


class Driver:
    def __init__(self, page):
        self.page = page
        self.x, self.y = SIZE["width"] / 2, SIZE["height"] / 2

    def click(self, locator, pause=0.35):
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        x, y = box["x"] + min(box["width"] / 2, 120), box["y"] + box["height"] / 2
        self.page.mouse.move(x, y, steps=8)
        self.x, self.y = x, y
        time.sleep(0.12)
        self.page.mouse.click(x, y)
        time.sleep(pause)

    def button(self, text):
        return self.page.get_by_role("button", name=text).first

    def scroll(self, dy):
        self.page.mouse.wheel(0, dy)
        time.sleep(0.4)


class Preview:
    def __init__(self):
        self.port = free_port()
        self.proc = None

    def __enter__(self):
        env = {**os.environ, "PORT": str(self.port), "PREVIEW_CLOCK_CONTROL": "1"}
        self.proc = subprocess.Popen(["node", str(ROOT / "scripts" / "preview_app.js")], env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.proc.stdout.readline()  # the "preview on" line means it is listening
        return f"http://127.0.0.1:{self.port}/"

    def __exit__(self, *exc):
        self.proc.terminate()
        self.proc.wait()


def to_gif(webm, out, start):
    palette = webm.with_suffix(".png")
    scale = f"fps={GIF_FPS},scale={SIZE['width']}:-1:flags=lanczos"
    common = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", str(GIF_MAX_SECONDS), "-i", str(webm)]
    subprocess.run(common + ["-vf", f"{scale},palettegen=stats_mode=diff", str(palette)], check=True)
    subprocess.run(common[:-2] + ["-i", str(webm), "-i", str(palette), "-lavfi",
                   f"{scale}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                   str(out)], check=True)
    size = out.stat().st_size
    if size > GIF_MAX_BYTES:
        sys.exit(f"{out.name} is {size} bytes, over the {GIF_MAX_BYTES} byte budget")
    print(f"wrote {out.relative_to(ROOT)} ({size // 1024} KB)")


def save_png(page, out, full_page=False):
    page.screenshot(path=str(out), full_page=full_page)
    img = Image.open(out).convert("RGB")
    bg = Image.new("RGB", img.size, img.getpixel((2, img.height - 2)))
    box = ImageChops.difference(img, bg).getbbox()
    if box:  # trim the empty page background below the content
        img = img.crop((0, 0, img.width, min(img.height, box[3] + 16)))
    img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    img.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


def record(browser, url, name, scenario):
    """Run scenario(page, driver) in a fresh recorded context, save the GIF from mark onward."""
    tmp = Path(tempfile.mkdtemp())
    ctx = browser.new_context(viewport=SIZE, record_video_dir=str(tmp), record_video_size=SIZE)
    ctx.add_init_script(CURSOR_JS)
    page = ctx.new_page()
    t0 = time.monotonic()
    page.goto(url)
    page.get_by_role("button", name="Start review").wait_for()
    time.sleep(0.6)
    start = time.monotonic() - t0
    scenario(page, Driver(page))
    time.sleep(1.5)
    length = time.monotonic() - t0 - start
    print(f"{name}: {length:.1f} s")
    if length > GIF_MAX_SECONDS:
        ctx.close()
        sys.exit(f"{name} runs {length:.1f} s, over the {GIF_MAX_SECONDS} s budget")
    video = Path(page.video.path())
    ctx.close()
    to_gif(video, ASSETS / name, start)
    shutil.rmtree(tmp, ignore_errors=True)


def hero(page, d):
    d.click(d.button("Start review"), pause=1.2)
    d.click(page.get_by_text("Train a logistic regression model with CREATE MODEL", exact=False), pause=0.6)
    d.click(d.button("Submit answer"), pause=1.8)
    d.click(page.get_by_role("button", name="Explanation").first, pause=1.4)
    d.scroll(260)
    time.sleep(2.5)


def take_mock_test(page, d, key, dwell=0.12, count=10, wrong=(3, 7)):
    d.click(d.button("Start Mock Test"), pause=0.6)
    if count != 10:
        page.get_by_label("Questions").fill(str(count))
    d.click(page.get_by_role("button", name="Start", exact=True), pause=0.6)
    resume = page.get_by_role("button", name="Resume")
    if resume.count():
        d.click(resume, pause=0.6)
    for n in range(count):
        text = page.inner_text("main")
        question = next(q for q in key if q in text)
        labels = page.locator("label.choice")
        choices = [labels.nth(i).inner_text().split(") ", 1)[-1] for i in range(labels.count())]
        picks = key[question] if n not in wrong else wrong_choices(choices, key[question])[:1]
        for pick in picks:
            d.click(page.locator("label.choice", has_text=pick).first, pause=dwell)
        if n == 2 and count > 2:
            d.click(d.button("Flag"), pause=0.5)
        if n < count - 1:
            d.click(d.button("Next"), pause=dwell)
    d.click(page.locator("button.submitbtn"), pause=0.8)
    d.click(page.locator("button.go", has_text="Submit test"), pause=1.2)
    page.get_by_text("Score by Section").wait_for()


def main():
    for tool in ("node", "ffmpeg"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is not on PATH")
    ASSETS.mkdir(parents=True, exist_ok=True)
    key = answer_key()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        with Preview() as url:
            record(browser, url, "hero-review.gif", hero)

        with Preview() as url:
            def mock(page, d):
                take_mock_test(page, d, key, count=4, wrong=(2,))
            record(browser, url, "mock-test.gif", mock)

        with Preview() as url:  # stills, unrecorded
            ctx = browser.new_context(viewport=SIZE)
            page = ctx.new_page()
            page.goto(url)
            d = Driver(page)
            # Four tests a few days apart, improving, so the history chart has a trend.
            for wrong in ((0, 2, 4, 6, 8), (1, 4, 6, 9), (3, 7), (5,)):
                page.goto(url)
                take_mock_test(page, d, key, dwell=0.02, wrong=wrong)
                if wrong == (3, 7):
                    save_png(page, ASSETS / "results.png")
                    d.click(page.get_by_role("button", name="Report").first, pause=0.6)
                    page.locator("textarea").first.fill("Should the hyperparameters count as a third answer here?")
                    page.locator("textarea").first.evaluate("e => e.scrollIntoView({block: 'center'})")
                    save_png(page, ASSETS / "report.png")
                urllib.request.urlopen(urllib.request.Request(url + "dev/advance?days=4", method="POST"))
            page.goto(url)
            d.click(page.get_by_text("Mock Test history"), pause=0.8)
            save_png(page, ASSETS / "history.png")
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
