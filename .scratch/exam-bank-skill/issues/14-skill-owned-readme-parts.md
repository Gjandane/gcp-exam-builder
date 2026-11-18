# 14: Skill-owned README parts

Spec: [0001, README parts](../../../docs/specs/0001-exam-bank-skill.md#readme-parts), [Confirm at build](../../../docs/specs/0001-exam-bank-skill.md#confirm-at-build)

**What to build:** A reader who knows a terminal, git, Python and Claude Code can follow the root README from clone to an exported CSV. This ticket writes the parts spec 0001 owns: Intro, Prerequisites, Part 1, the skill side of Upkeep and Troubleshooting, Notes and License. Part 2 and the app side belong to spec 0002 and get a marked slot.

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13

**Status:** resolved

**Model tier:** light
**Effort:** medium
**Where:** cli
**Constraints:** Follow the spec's rules for every part: only what the reader types, clicks or edits, every rule a link to a spec section, no question site named, no screenshots, no FAQ. Write no Part 2 text. The permission block has one copy, printed by setup.

- [x] Confirm-at-build 9 is settled: the repository URL for the clone line. With no remote yet, ask the user
- [x] Confirm-at-build 10 is settled and recorded in the ticket comments: whether Google's sample-question form shows correct answers after submit
- [x] Sections 1, 2 and 3 hold the content the spec lists, with the step table
- [x] Shell commands are given for bash, with the PowerShell form beside any that differs
- [x] The `python` command name matches what ticket 03 confirmed
- [x] Sections 5 and 6 hold the skill-side lines only, each linked to its spec section
- [x] Section 7 holds the notes and the license line
- [x] A marked slot stands where spec 0002's Part 2 and app-side lines go

**Verify:**

- Every command in the README runs as written on a fresh clone, in bash and in PowerShell, up to the first `/exam-bank pmle`
- Every spec link resolves to an existing heading
- Search the README for the Curated site and LLM-scrape source names. None appears
- User: read Part 1 top to bottom and follow it on a clean folder until setup passes

## Comments

- 2026-11-18, confirm-at-build 9: user authorized creating a repository. Created private https://github.com/Gjandane/gcp-exam-builder, configured origin, and verified the HTTPS clone URL in bash and PowerShell.
- 2026-11-18, confirm-at-build 10: user confirmed, "It reveals the correct answers" after submission of Google's official sample-question form. Tick the revealed answers when entering samples through given/; follow the intake spec for any answer the form does not reveal.
- Verify 1: ran the README's commands through config creation on separate fresh GitHub clones in Git Bash and PowerShell. Both setup probes passed with Python 3.11.5. Installed clasp under an isolated npm prefix.
- Verify 2 and 3: all 43 local links resolve, including every spec heading; no configured Curated-site or LLM-scrape source name appears in README.
- Verify 4: user delegated the clean-folder walkthrough. A fresh Claude Code session ran /exam-bank pmle in the PowerShell clone, read only 01-setup.md, printed Setup passed, and recorded setup.passed_at. Merged the printed permissions into that clone's local settings. No permission denials.
- Full suite: 366 passed. Independent Standards and Spec reviews: no findings.

## Build notes

- Added root README; no Modules, Interfaces or cross-module calls changed.
