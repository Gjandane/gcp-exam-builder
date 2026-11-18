Status: done

## Concern
Make the root `README.md` more attractive and user friendly, with screenshots and GIF animations, so visitors understand the project fast and star the repo. Both specs (0001 skill, 0002 study app) are built and deployed.
Round 2 (2026-11-18): redo the specs and tickets for the remaining work (old tickets 05 to 08). The user screenshots nothing and only approves permissions. Most tickets run in parallel sessions.
Folder: .scratch/readme-visuals/

## Settled decisions
- D1: Amend README rules in 0001 and 0002: allow screenshots, GIFs and a showcase section (hero, features, how it works) above Part 1. Reverses D338; without the amendment a spec-driven rebuild strips the visuals.
- D2: Every visual comes from a synthetic **Demo bank** (about 20 to 30 original PMLE-style questions with real explanations), never the real bank. Real bank is scraped third-party content. **Demo bank**
- D3: Mask email, avatar, sheet ID, script ID and `/exec` URL in every capture before it enters the repo. One rule for all images.
- D4 (Prerequisite): `git rm` `reference_pictures/` before the README change. Filenames name question sites; README names no site. History not purged.
- D5: Two-layer README: visual top half for any visitor, existing exact steps below for the terminal-savvy reader. Hook plus precision without a beginner rewrite.
- D6: Hero GIF shows **Review mode**: pick answer, graded, per-choice explanations, under 15 s. Shows the core payoff.
- D7: App visuals recorded by a Playwright script on the local preview shim, converted to GIF with ffmpeg; agent runs it. Repeatable, no personal data.
- D8: Commit the preview shim and capture script under `scripts/`, covered by `docs/checks.md` checks. One-command refresh when UI changes.
- D9: Agent writes the **Demo bank**: 25 original questions, 5+ **Subdomains**, **Lineage** `created`, real explanations, 1-2 **Uncertain answers**, at `docs/demo/demo-bank.csv`; must pass Bank check; user reviews.
- D10: Skill side shown by a Mermaid pipeline diagram (sources → 10 steps → CSV → Sheet app) plus one real terminal screenshot of a step summary. Real run too long and costly for a GIF.
- D11: User screenshots only the unverified-app screen and the Deploy dialog; agent crops and masks per D3. Reassures at the scariest step.
- D12: Assets in `docs/assets/`; GIFs ≤ 960 px wide, ≤ 15 s, ≤ 3 MB; PNGs optimized.
- D13: Badges under title: License MIT, `Checks` CI, Claude Code skill, Google Apps Script.
- D14: Agent makes `docs/assets/social-preview.png` 1280×640 and drafts About text and topics; user uploads and sets them in GitHub Settings.
- D15: One legal line under the hero ("Personal use only · Not affiliated with Google · details"); full Notes section kept.
- D16: README gets a "Try it in 5 minutes" path: deploy app (Part 2), import `docs/demo/demo-bank.csv`, practice. Fastest route to the payoff, no Opus spend.
- D17: Top-half order: title + badges → tagline → hero GIF → legal line → 4-tile feature grid → How it works diagram → Try it in 5 minutes → table of contents → Parts 1-2. Hook, proof, action.
- D18: Feature tiles: **Review mode** with explanations; **Mock Test** GIF (timer, **Flag**, submit); results by **Section**; History and **Report** loop.
- D19: Upkeep, Troubleshooting and PowerShell variants go in `<details>` blocks. Shorter page, nothing lost.
- D20: Tagline: "Build your own Google Cloud certification question bank with Claude Code, then drill it in a free Google Sheets exam simulator."
- D21: One star call-to-action line ends the showcase: "If this helps you pass, a ⭐ helps others find it."
- D22: 0001 owns showcase, badges, legal line, diagram, social preview; 0002 owns app GIFs, feature tiles, Demo bank import path, Part 2 screenshots. Matches the existing split.
- D23: Delivery: amend both specs' README parts, then tickets in `.scratch/readme-visuals/issues/`, ordered: remove `reference_pictures/` → Demo bank → preview shim → capture script → user's Google screenshots → README → social preview.
- D24: User runs `/exam-bank pmle export` and screenshots the summary; agent crops and masks site names and paths (extends D3). Cheapest real step, shows the finished result.
- D25: **Demo bank** is a PMLE bank using the **Sections** and **Subdomains** of `pmle.example.yaml`; README prints its `section_weights` line. One exam across the repo; Settings accepts it unchanged.

- D26: Round 2 continues this log at D26+. Old tickets 05 to 08 are marked superseded; new tickets start at 09. Keeps every RV-Dn citation valid.
- D27: The user captures nothing and only approves permissions. Supersedes the "user captures" parts of D11 and D24, and the "user uploads and sets" part of D14.
- D28: Export summary image: the agent runs `eb.py export pmle` on the real bank, masks site names and paths in the text, and renders a terminal-style PNG with a committed Playwright script. Supersedes the screenshot part of D10 and D24. Text masking beats pixel masking.
- D29: Unverified-app image: the agent makes a throwaway sheet with `clasp create-script`, opens it in Chrome, takes a desktop screenshot of the OAuth popup with the Claude window moved aside, then crops and masks per D3. The user approves tool access and clicks Advanced and Allow in the popup. Supersedes D11's capture method.
- D30: The same live session checks the Try it path on the throwaway sheet: import `docs/demo/demo-bank.csv`, set "PMLE (demo)" Settings, answer one Review question, then move the sheet to Trash. One Google session, one round of approvals.
- D31: The agent does every GitHub action (About, topics, social preview upload via Claude in Chrome, repo rename, public repo create, push), each after one yes in chat. Supersedes the user steps in D14 and old ticket 08.
- D32: The private repo is renamed `gcp-exam-builder-archive`. The new public single-commit repo takes `gcp-exam-builder`.
- D33: Parallel split. Wave 1, all at once: live Google captures and Try it check (main checkout, GUI); export summary image (main checkout, reads the real bank); social preview and About draft (worktree); README rewrite with fixed asset filenames (worktree); three fixture tickets, one each for examtopics, certsafari, merge and export (worktrees). Wave 2: publish. Disjoint files run in parallel; GUI and gitignored inputs pin two tickets to the main checkout.
- D34: Allow rules in `.claude/settings.local.json` for routine local commands (checks, pytest, `npm test`, `node scripts/*`, `python scripts/*`, local git). Push, `gh repo create/edit/rename`, clasp and Chrome or desktop access still prompt.

- D35: Once the new unverified image is in `docs/assets/`, delete `exam-bank/screens/` and move the "Demo screenshots 2" sheet to Trash. Removes captures that hold the user's email; Trash stays recoverable.
- D36: Publish starts by pushing `readme-visuals` to the private repo and checking the README render (images, Mermaid, anchors) in Chrome. Breakage is found while the repo is still private.
- D37: Before publish, fast-forward `master` to `readme-visuals`, push it to the archive, and build the single public commit from that tree. Archive and public repo start from the same tree.

## Open questions

## Parked

## Facts found
- `docs/specs/0001-exam-bank-skill.md:1069-1074`: README rules: reader is terminal-savvy; README repeats only what the reader types, clicks or edits; "No screenshots, no step rules, no CSV schema, no per-source scraping detail, no FAQ, no contributing guide"; README names no question site.
- `docs/specs/0002-study-app.md:961`: "Screenshots in the README" listed out of scope (D338).
- `docs/specs/0001-exam-bank-skill.md:1067`: README section ownership split: 0001 owns Intro, Prereqs, Part 1, Notes; 0002 owns Part 2 and app side of Upkeep/Troubleshooting.
- `exam-bank/pmle/bank.jsonl`: real bank, 27 scraped third-party questions, gitignored. Not safe to show.
- `app/tests/fixtures/fixture-bank.csv`: 13 rows, placeholder explanations ("Why this choice fails."). Safe but looks fake.
- `reference_pictures/`: 4 PNGs tracked in git, 3 named after question sites.
- `certsafari-live-temp.html`: untracked root file, names a question site. Keep out of commits.
- `README.md`: 195 lines, 7 numbered sections, no images, no badges, no hero.
- No `ARCHITECTURE.md`. Repo: github.com/Gjandane/gcp-exam-builder.
- `app/client/index.html`: only file with scriptlets (7 `include_` lines); regex-inlinable.
- `app/client/*.html`: 14 `google.script.run` calls, success/failure handlers only; no `google.script.host`, no external scripts. A Proxy stub covers all.
- `app/server/main.js`, `server.js`, `sampler.js`: wrappers call `makeServer_(adapter)`; no Apps Script globals in server/sampler.
- `app/tests/load-server.js`, `fake-adapter.js`, `bank-fixture.js`: in-memory backend usable from Node. Local preview feasible with ~50-60 line Node shim (POST /rpc/fn → makeServer(fake)[fn]).
- Local preview limits: fake spreadsheet/web-app URLs; no Google iframe banner; fixed `now` must be set for timer/dates.
- `.scratch/gcp-exam-sim/prototypes/`: empty, no mockups.
- Tools: ffmpeg on PATH; Node 24; Playwright via requirements.txt; no vhs, agg or asciinema.
- `.github/workflows/check.yml`: workflow name `Checks`, runs on push and PR.
- Round 2 facts (2026-11-18):
- `docs/assets/`: hero-review.gif, mock-test.gif, results.png, report.png, history.png, deploy-dialog.png done. Missing: unverified-app image, export summary image, social preview.
- `exam-bank/screens/unverified-5.png` (gitignored, 2880×1620 desktop capture): has the "Google hasn't verified this app" popup, but the Claude desktop window covers its right side; body text cut. Frames hold the user's email. "Demo screenshots 2" sheet already authorized, so Google will not show the screen again for it.
- `deploy-dialog.png` came from a Claude in Chrome screenshot blob, copied from the session's `tool-results/` folder. The OAuth popup is a separate Chrome window: desktop (computer-use) screenshot needed; Chrome is read tier there, so the agent cannot click in it.
- `.claude/skills/exam-bank/steps/10-export.md`: export is `python .claude/skills/exam-bank/scripts/eb.py export <exam>`; the summary is its stdout. No human needed to produce it.
- Gitignored inputs (`exam-bank/`, `.claude/launch.json`) do not exist in a worktree. Tickets that read them run in the main checkout.
- Only one session at a time can drive Chrome or the desktop.
- `gh` logged in as repo owner. Repo is PRIVATE, description "Personal Google Cloud certification study workflow", no topics. `clasp` on PATH.
- Site-saved fixtures to replace (old 08 decision 1): `examtopics/page-1.html`, `examtopics/gate.html`, `certsafari/practice-questions.html` (+ `build_fixture.py`), `merge/sources/{certsafari,examtopics}.jsonl`, `merge/bank.jsonl`, `export/bank.jsonl`, `export/pmle-questions.csv`, under `.claude/skills/exam-bank/scripts/tests/fixtures/`.
- Old 08 decisions (user, 2026-11-18): synthetic fixtures; fresh single-commit public repo, private repo kept as archive, no history rewrite; keep site-named scrapers; publish `.scratch/`. So the blur-masked deploy-dialog in history is moot.
