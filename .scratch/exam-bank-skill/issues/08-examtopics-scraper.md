# 08: ExamTopics scraper

Spec: [0001, Step 2: scrape](../../../docs/specs/0001-exam-bank-skill.md#step-2-scrape), [Confirm at build](../../../docs/specs/0001-exam-bank-skill.md#confirm-at-build). Research: `.scratch/gcp-exam-sim/research/examtopics-pmle.md`

**What to build:** The user runs the scrape step, a browser window opens, the user logs in to ExamTopics when asked, and the script saves every page's questions with the site answer and the community answer. A rerun continues from the last saved page. This ticket also builds the rules every Curated site scraper shares.

**Blocked by:** 01, 03, 07

**Status:** resolved

**Model tier:** standard
**Effort:** high
**Where:** cli
**Constraints:** The script obeys `robots.txt`, types no credentials and solves no CAPTCHA. No discussion requests and no vote shares. One page at a time with the spec's random pause. `parse_page` stays apart from the Playwright driver. The live Verify steps need the user present with a headed browser and their own login. Fixture HTML comes from the first live capture. Scrub any account detail from it before saving it as a fixture.

- [x] Confirm-at-build 1 is settled first and recorded in the ticket comments: selectors, the page-count line, and whether the answer and the "Most Voted" tag sit in the DOM without a click
- [x] The scrape command runs the scraper of every enabled Curated site with pages left, with a persistent browser profile per site
- [x] A login gate or challenge writes the gate with its exact action into the state file, keeps the window open and polls as the spec says. Cards appearing clears the gate. A timeout closes and exits
- [x] After each page the script saves the raw HTML, appends the page's records and updates the progress file
- [x] `parse_page` returns number, stem, choices, site answer and community answer per question
- [x] A question with an image or a choice count out of range is skipped and logged
- [x] Text is stored under the cell text rule: plain text, code in backticks
- [x] Pages run from the config URL to the page count read from the page
- [x] The source table in `state.md` shows pages done over total and `waiting on user` with the action
- [x] The scrape step file starts the command in the background and waits for it

**Verify:**

- Run `pytest`. `parse_page` on saved fixture pages returns the expected records, including a question with no "Most Voted" tag and a skipped image question
- A gate test with a fixture login page sets the gate in the state file
- User present: run `/exam-bank pmle scrape` in a fresh session and log in when the window asks. The run saves at least three pages and the progress file counts them
- User present: stop the run, start it again. It continues from the next unsaved page
- Run merge on the result. Rows in the bank file carry an `examtopics` source record with `site_answer`, and `community_answer` where the page had a "Most Voted" tag

## Comments

- 2026-11-17, Confirm-at-build 1 (live check of page 1 and the anonymous page 2 in the browser pane, no login):
  - Cards: `div.exam-question-card` inside `.questions-container`, 10 per page. Number: `.card-header strong` "Question #N". Stem: `p.card-text` inside `.question-body`, lines split by `<br>`. Choices: `li.multi-choice-item`, letter in `.multi-choice-letter[data-choice-letter]`, text is the rest of the `li`.
  - Page count: `Viewing page 1 out of 38 pages.` in `.pagePagging__left span`.
  - Site answer: `.question-answer` holds `Correct Answer:` then `strong.ml-1` with the letter. It sits in the DOM before any click. `doRevealSolution` only shows it and removes `d-none` from the badge.
  - "Most Voted": `span.most-voted-answer-badge` inside the voted option's `li`, hidden by `d-none`, present in the DOM with no click. A line "Community vote currently supports Answer X" and a `data-chart` vote list also exist; neither is read (no vote shares).
  - All 10 page-1 cards carry the badge on the same letter as the site answer, so a card with no badge and a badge that differs from the site answer are not yet seen. The live run settles both.
  - Gate: anonymous `/view/2/` has zero `.exam-question-card` and no "Viewing page" line. It says "Step 2 of 3 - Create your account". Page 1 holds a hidden login modal, so the modal is not a gate signal. Gate = zero cards.
  - Not yet seen: image question markup, multi-answer markup, where login lands. The first live run records them.
- 2026-11-17, live run (user present, headed browser, own login): pages 1 to 3 saved, `progress.json` shows 3/38, 27 records (30 cards, 3 image questions skipped and logged). Rerun loaded page 4 without refetching 1 to 3.
  - Free accounts see Questions 1 to 30 only. Page 3 is preceded by a "Continue with my final 10 free questions" interstitial the user clicks. Page 4 needs Contributor Access or PRO, so the gate stays set and the full 38 pages are out of reach without it. Nothing bypasses it.
  - Image questions: the image sits in `p.card-text`. Every card also holds a vote icon `img` in `.question-answer`, which is not content. The image check looks at stem and choices only.
  - Multi-answer cards print `Correct Answer: AD` and tag no option "Most Voted", so `community_answer` is empty for them even though the page says the community supports AD. Spec rule kept. The "Community vote currently supports Answer X" line could fill it if the user wants.
  - Source text holds mojibake (`ג€` for curly quotes). Stored verbatim per the spec, so these IDs will not match a copy with proper quotes.
  - Verify 3 and 4 ran `eb.py scrape pmle` directly, not through `/exam-bank` in a fresh session. Verify 5: `merge` gave 27 rows, each with an `examtopics` source record and `site_answer`; 26 carried `community_answer` (Q28, the multi-answer one, had none until the line fallback below; then all 27).
  - Fixtures are real markup with neutral text (real questions are not committed). The multi-answer, no-tag and image shapes were checked against the live raw pages. Implementation commit: `d01e086`.

## Build notes

- Added `scrape.py`, `scrapers/common.py` (shared Curated site rules) and `scrapers/browser.py` (Playwright driver); `eb.py scrape` now runs.
- Interface: each scraper module exposes `page_url`, `has_cards`, `page_count`, `on_auth_page`, `parse` and `parse_page`; `common.run_site` takes a session with `load`, `snapshot`, `url`, `get_text`.
- New calls: `scrape.run` to `common.run_site`; `common.set_gate` writes the `gates` key of `state.json`.
- Mismatch: ExamTopics free accounts stop at page 3 of 38, which the spec's "Page 2 onward needs the user's login" does not say; spec Step 2 and the `scrape` done rule need a note.
- Mismatch: multi-answer cards carry no "Most Voted" tag. User decided 2026-11-17 to fall back to the "Community vote currently supports Answer X" line there; spec Step 2 community rule needs that added.
