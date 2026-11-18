# 10: Export summary image

Spec: [0001, 0 Showcase](../../../docs/specs/0001-exam-bank-skill.md#0-showcase), [0001, Visual rules](../../../docs/specs/0001-exam-bank-skill.md#visual-rules). Log: RV-D10, RV-D28.

**What to build:** One command writes `docs/assets/export-summary.png`: the real `export` summary in a terminal-style frame, with question-site names and local paths masked.

**Blocked by:** none

**Status:** done

**Model tier:** standard
**Effort:** low
**Where:** cli
**Constraints:** Main checkout, never a worktree (reads the gitignored real bank in `exam-bank/pmle/`). No GUI. Mask on the text, before rendering: replace each configured source name (from the exam config) with a generic label such as `source-1`, and each absolute or user path with a short repo-relative one. Never print question text. Write only the new script, its test, the PNG, the "README visuals" list in `docs/checks.md` and this ticket.

- [x] `scripts/render_export_summary.py`: runs `python .claude/skills/exam-bank/scripts/eb.py export <exam>` (default `pmle`), captures stdout, masks it, renders it with Playwright as a dark terminal window under a `/exam-bank pmle export` prompt line, saves the PNG
- [x] Run command in the script header; one line added under "README visuals" in `docs/checks.md`
- [x] PNG at most 960 px wide, optimized, legible at README width
- [x] A pytest covers the masking function: site names and paths in, none out

**Verify:**

- Open the PNG at full size: no site name, no path outside the repo, no question text
- Rerun: same image
- Checks in `docs/checks.md` pass

## Build notes

- Added `scripts/render_export_summary.py` (`mask`, `source_names`, `render`) and `scripts/tests/test_render_export_summary.py` (earlier commit).
- Bank now exports; `python scripts/render_export_summary.py` wrote `docs/assets/export-summary.png` (900x381, PIL-optimized, 20 KB). Rerun gave a byte-identical file.
- Masked text checked: no configured source name, no absolute path, no question text. `scripts/check.py` passes.
