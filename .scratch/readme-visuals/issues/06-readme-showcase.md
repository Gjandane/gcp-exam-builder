# 06: README showcase and restructure

Spec: [0001, README parts](../../../docs/specs/0001-exam-bank-skill.md#readme-parts), [0002, README parts](../../../docs/specs/0002-study-app.md#readme-parts). Log: RV-D5, RV-D13, RV-D15 to RV-D22.

**What to build:** The root README opens as a product page and keeps the exact steps below it, with the long parts collapsed.

**Blocked by:** 01, 02, 04, 05

**Status:** wontfix

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Follow the Showcase order in 0001 exactly. Below the Showcase, change only the `<details>` wrapping and the two Part 2 images. Name no question site.

- [ ] Badges: License MIT, `Checks` CI, Claude Code skill, Google Apps Script
- [ ] Tagline, hero GIF, legal line and the four tiles
- [ ] Mermaid diagram plus the export screenshot
- [ ] Try it path with the Demo bank `section_weights` line from ticket 02
- [ ] Star line and table of contents
- [ ] Upkeep, Troubleshooting and PowerShell variants in `<details>`
- [ ] Part 2 step 2 and step 3 images placed
- [ ] Notes and License section kept whole

**Verify:**

- Render on GitHub from a pushed branch: images load, Mermaid renders, every anchor and spec link resolves
- Search the README for every configured source name: none appears
- Follow the Try it path on a fresh sheet with `docs/demo/demo-bank.csv`

## Comments

- 2026-11-18: Superseded by tickets 12 (readme-visuals RV-D26). The agent now does every capture and GitHub action; the user only approves.
