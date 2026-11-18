# 11: Social preview and About draft

Spec: [0001, 0 Showcase](../../../docs/specs/0001-exam-bank-skill.md#0-showcase). Log: RV-D14, RV-D31.

**What to build:** `docs/assets/social-preview.png` (1280×640) plus a drafted About line and topics, ready for ticket 16 to apply.

**Blocked by:** none

**Status:** resolved

**Model tier:** standard
**Effort:** low
**Where:** cli
**Constraints:** Worktree. No GUI, no GitHub calls. Build the image from committed files only: a frame of `docs/assets/hero-review.gif` (Demo bank content) plus the title and the tagline from 0001 Showcase item 2. Render with Playwright from a small HTML template; commit the generator under `scripts/`. Write only the generator, the PNG, the "README visuals" list in `docs/checks.md` and this ticket.

- [x] `docs/assets/social-preview.png`, exactly 1280×640, under 1 MB
- [x] Title and tagline legible when scaled to 400 px wide
- [x] Generator under `scripts/`, run command in its header, listed under "README visuals" in `docs/checks.md`
- [x] About line (at most 120 characters, names no question site) and 5 to 10 topics written in this ticket's comments

**Verify:**

- Open the PNG at full size and at 400 px wide: text legible, nothing cut off
- Checks in `docs/checks.md` pass

## Build notes

- Added `scripts/build_social_preview.py` (Pillow + Playwright; frame 40 of hero-review.gif); listed in `docs/checks.md`.
- `npm test` has 1 failure (bank-check import-steps CRLF vs LF; core.autocrlf=true on this Windows checkout), unrelated to this ticket.

## Comments

- About (112 chars): Build a Google Cloud certification question bank with Claude Code, then drill it in a free Sheets exam simulator.
- Topics: google-cloud, gcp, certification, exam-prep, question-bank, claude-code, claude-code-skill, google-apps-script, google-sheets, study-app
