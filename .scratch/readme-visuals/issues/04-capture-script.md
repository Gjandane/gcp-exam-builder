# 04: Capture script and app images

Spec: [0002, Visuals, app side](../../../docs/specs/0002-study-app.md#visuals-app-side), [0001, Visual rules](../../../docs/specs/0001-exam-bank-skill.md#visual-rules). Log: RV-D6, RV-D7, RV-D12, RV-D18.

**What to build:** One command records the hero GIF and the four feature-tile images from the preview server into `docs/assets/`.

**Blocked by:** 02, 03

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Playwright drives the preview. ffmpeg makes each GIF with a palette pass. A GIF is at most 960 px wide, 15 s and 3 MB. PNGs optimized.

- [x] Hero GIF: **Review mode**. Pick an answer, see it graded, read the per-choice explanations. Under 15 s
- [x] Tiles: Review mode with explanations; a **Mock Test** GIF with timer, **Flag** and submit; results by **Section**; History and the **Report** loop
- [x] Script under `scripts/`, with its run command in the script header
- [x] No fake URL, email or path visible in any frame

**Verify:**

- Rerun from clean: same files, each inside the size budget
- Step through every GIF frame for anything that must be masked

## Comments

- 2026-11-18: `python scripts/capture_readme.py` writes `docs/assets/hero-review.gif` (720 px, ~11 s, ~2.3 MB), `mock-test.gif` (4-question test, ~11 s, ~2.1 MB, ends on results), `results.png`, `report.png`, `history.png` (four tests 4 days apart, 50% → 90%). GIFs 720 px wide, 8 fps; a blue dot shows the cursor. A GIF over the size or length budget stops the script.
- Frames reviewed: only Demo bank content, no URL bar, email or path. Ran before the user's Demo bank review (user chose to run 01-04 first); rerun after any bank edit.
