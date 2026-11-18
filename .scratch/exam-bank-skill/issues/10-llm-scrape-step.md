# 10: LLM-scrape step

Spec: [0001, Step 3: llm-scrape](../../../docs/specs/0001-exam-bank-skill.md#step-3-llm-scrape), [Confirm at build](../../../docs/specs/0001-exam-bank-skill.md#confirm-at-build). ADR 0004.

**What to build:** The user runs the llm-scrape step. A script downloads each enabled static source page, a subagent extracts the questions from the saved text, and the script rejects any question whose text is not on the page. A page that fails is listed with its reason and the step still finishes.

**Blocked by:** 01, 04, 07

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** ADR 0004: the script fetches, the subagent only extracts and has no web tool. No user detail goes into any request. The worker copies text verbatim, typos included. The user runs the live Verify step in a fresh session.

- [x] Confirm-at-build 3 is settled and recorded in the ticket comments: whether Whizlabs, TheServerSide and Open Exam Prep carry the question text in static HTML
- [x] The fetch command checks `robots.txt`, downloads with the spec's User-Agent, and saves the HTML, the text and a meta file per page
- [x] Every page gets a meta file, on failure too, with the failure reasons the spec names
- [x] An unchanged page with a valid result is skipped. A page that failed before is fetched again
- [x] One Batch is one page. The batches command runs fetch first
- [x] The worker file holds the extraction rules and the shared frame, on the reader agent type
- [x] Validation finds the stem, every choice and every explanation in the saved text after normalization, and checks answer letters
- [x] A page with zero `ok` questions is failed. After attempt 3 the valid questions are kept, the rest dropped and listed, and the page counts as done
- [x] Apply writes the per-source file. A changed page replaces its own records
- [x] An explanation given as one block is stored as the source's explanation block
- [x] The llm-scrape step file exists and follows the dispatch procedure
- [x] One fixture input file for a manual worker run ships with the tests

**Verify:**

- Run `pytest`. Fetch tests against a local fixture server or mocked responses cover robots, non-200, too large and unchanged. Validation rejects a reworded stem
- Run the fetch command on the PMLE config. Each enabled page has a meta file with `ok` or a failure reason
- User, in a fresh session: run `/exam-bank pmle llm-scrape`. The step ends done, the MockingOwl source has questions, and any failed page shows in `state.md` with its reason
- Run merge. In the bank file, a row whose answer only an untrusted source gives has `uncertain` true

## Comments

- Confirm-at-build 3 settled 2026-11-17 by a live fetch of all four pages with the spec User-Agent: Whizlabs, TheServerSide, MockingOwl and Open Exam Prep all carry question and choice text in static HTML. Whizlabs and MockingOwl give about 20+ questions, Open Exam Prep prints "Loading practice questions..." yet the server HTML holds numbered questions with explanations, and TheServerSide uses `A.` choice lines. TheServerSide sends no charset, so `requests` guessed Latin-1 and garbled quotes. The fetch decodes UTF-8 first.
- Verify results: `pytest` passes (fetch: robots, non-200, network, too large, unchanged; validation rejects a reworded stem; merge marks an untrusted-only answer `uncertain`). The fetch command ran live on the PMLE config: all four pages `ok`.
- Unrun: the live `/exam-bank pmle llm-scrape` run in a fresh session (needs the user and real subagents). The worker has no automated test; `tests/fixtures/workers/llm-scrape.in.json` plus its page text is for a manual run.

## Build notes

- Added `fetch.py` (fetch command) and `llm_scrape.py` (batch forming, validation, apply); `eb.py` gains `fetch`; `batches.run/apply` hand step `llm-scrape` to `llm_scrape`.
- `state.py` now counts an llm-scrape page done from its meta file (`failed: ...`, `done-partial`, or `applied`) instead of scanning the manifest.
- Meta files gain an `applied` field (Batch id) beyond the spec's four fields; the unchanged-page skip keys on it.
- Retry inputs gain an optional `only` list of rejected question numbers; the worker file honours it. Not in the spec.
- A page whose attempt-3 entry has no parseable result stays `failed` in the Batch counts and is retried from attempt 1 on the next run, rather than being counted done.

