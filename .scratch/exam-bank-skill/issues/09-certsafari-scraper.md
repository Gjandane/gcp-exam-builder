# 09: CertSafari scraper

Spec: [0001, Step 2: scrape](../../../docs/specs/0001-exam-bank-skill.md#step-2-scrape), [Confirm at build](../../../docs/specs/0001-exam-bank-skill.md#confirm-at-build). Research: `.scratch/gcp-exam-sim/research/certsafari-pmle.md`

**What to build:** The scrape step also reads the CertSafari sample page: each question with its answer, one explanation per choice and the Subdomain label printed above its group. After merge those rows arrive with source explanations and, where the label matches the exam config, a Subdomain tag.

**Blocked by:** 01, 08

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Only the sample page. `robots.txt` disallows the quiz path. Reuse the shared scraper rules from ticket 08. The live Verify step needs the user present if the page needs a browser.

- [x] Confirm-at-build 2 is settled first and recorded in the ticket comments: whether answers and explanations sit in the static HTML, and the selectors
- [x] The scraper uses a plain HTTP fetch when the static HTML holds the answers, else the browser with a click per question
- [x] `parse_page` returns position number, stem, choices, answer letters, one explanation per choice and the raw Subdomain label
- [x] The record uses the page position as its question number
- [x] Skips, raw HTML, the per-source file and the progress file follow the shared rules

**Verify:**

- Run `pytest`. `parse_page` on the saved fixture page returns the expected records with explanations and labels
- User present: run `/exam-bank pmle scrape` in a fresh session. The source table shows CertSafari at 1 of 1 pages
- Run merge. Rows whose label matches the config have `subdomain_by: source`, and their explanations come from the source

## Comments

- 2026-11-17: Live browser DOM before clicking contains answers and explanations inside closed `details` elements. Each question is an `article` with a label in `p`, position and stem in `h3`, choices in `ol > li`, answer in `details > div > p`, and per-choice explanations in `details > div > ul > li`.
- The initial HTTP response is not confirmed: command-line DNS lookup failed, and the browser blocked `view-source:`. A saved original HTML response is needed to settle whether plain HTTP is sufficient.
- 2026-11-17, Confirm-at-build 2 settled (plain `curl` with the `exam-bank` UA, 200, 584 KB, no login, no challenge): the original HTTP response already holds all 35 `article` cards and 35 closed `details` blocks. No `img`. So plain HTTP is enough, no browser, no click.
  - Selectors: card `article`; label `article > p` (first child); position `h3 > span:first-child` ("N."); stem = `h3` minus its `span` children (a trailing `span` "(Select N)" is page decoration, dropped); choices `ol > li`, letter in the first `span`, text in the second; answer `details > div > p` own text "Correct answer(s): A, C" (React `<!-- -->` comments sit between its pieces); explanations `details > div > ul > li`, letter in the first `span`, the rest is the text and keeps its "Correct."/"Incorrect." opening.
  - The Subdomain label sits in each card, not once above a group. One label reads `2.1: Exploring and preprocessing data for ML.` with no "Subdomain" word; merge's label rule accepts both.
  - Live run through `scrape.run` then merge in a scratch root: 35 records, 1/1 pages, 35 bank rows, 147 source explanations, 31 rows tagged `subdomain_by: source`, 4 untagged (label not in the config).
  - Saved original response is kept outside the repo in the session notes folder (`certsafari-static.html`). The committed fixture is neutral text in the same markup, rebuilt by `tests/fixtures/certsafari/build_fixture.py`.

## Build notes

- Added `scrapers/certsafari.py` (`FETCH = "http"`) and `scrapers/http.py` (`HttpSession`, stdlib `urllib`, `interactive = False`); no module removed.
- `scrape._session_class` picks `HttpSession` or `BrowserSession` from the scraper's `FETCH`; `run_site` stops (no gate poll) when a non-interactive session gets no cards.
- `common.source_row` now writes per-choice `explanation` and `subdomain_label` from the record; `community_answer` defaults to `[]`.
- Mismatch: spec Step 2 puts the Subdomain line above a group, the live page repeats it in every card; spec says `requests`, build uses `urllib`.
- Unrun: `/exam-bank pmle scrape` in a fresh session (needs the user). Scrape and merge ran directly against the live page instead.
