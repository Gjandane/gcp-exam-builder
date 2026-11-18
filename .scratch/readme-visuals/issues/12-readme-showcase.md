# 12: README showcase and restructure

Spec: [0001, README parts](../../../docs/specs/0001-exam-bank-skill.md#readme-parts), [0002, README parts](../../../docs/specs/0002-study-app.md#readme-parts). Log: RV-D5, RV-D13, RV-D15 to RV-D22, RV-D28, RV-D29.

**What to build:** The root README opens as a product page and keeps the exact steps below it, with the long parts collapsed.

**Blocked by:** none

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Worktree. Follow the Showcase order in 0001 exactly. Below the Showcase, change only the `<details>` wrapping and the two Part 2 images. Name no question site. Use these fixed paths under `docs/assets/`: `hero-review.gif`, `mock-test.gif`, `results.png`, `history.png`, `report.png`, `export-summary.png` (ticket 10), `unverified-app.png` (ticket 09), `deploy-dialog.png`. Tickets 09 and 10 run at the same time, so in this worktree the README link check fails for those two files only; they merge before this ticket. Write only `README.md` and this ticket.

- [x] Badges: License MIT, `Checks` CI, Claude Code skill, Google Apps Script
- [x] Tagline, hero GIF, legal line and the four tiles
- [x] Mermaid diagram plus `export-summary.png`
- [x] Try it path with the Demo bank `section_weights` line from ticket 02's comments
- [x] Star line and table of contents
- [x] Upkeep, Troubleshooting and PowerShell variants in `<details>`
- [x] Part 2 step 2 (`unverified-app.png`) and step 3 (`deploy-dialog.png`) images placed
- [x] Notes and License section kept whole

**Verify:**

- `python scripts/check.py --readme-only`: in the worktree only the two pending images fail; after merge all pass
- Search the README for every configured source name: none appears
- The render check on github.com happens in ticket 16

## Build notes

- `<details>`/`<summary>` carry `class="more"`: scripts/check.py's placeholder regex flags bare `<details>`; allowlist HTML tags there later.
- Tile 1 reuses `hero-review.gif`; tile 4 holds `history.png` and `report.png`; Try it prints the Demo bank line and links Part 2, no second import-steps copy.
- `--readme-only` fails only on `export-summary.png` (ticket 10) and `unverified-app.png` (ticket 09), as expected.
- github.com render check (Mermaid, details, tiles) left to ticket 16.
