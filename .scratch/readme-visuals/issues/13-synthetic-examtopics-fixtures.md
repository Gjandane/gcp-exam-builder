# 13: Synthetic examtopics fixtures

Spec: [0001, Notes and License](../../../docs/specs/0001-exam-bank-skill.md#7-notes-and-license). Log: RV-D33; old ticket 08, decision 1.

**What to build:** The examtopics fixtures hold only invented questions, with the same page structure as before, so the public repo republishes no question-site content and every test still passes.

**Blocked by:** none

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Worktree. Files, under `.claude/skills/exam-bank/scripts/tests/fixtures/`: `examtopics/page-1.html`, `examtopics/gate.html`. Tests that read them: `test_examtopics_parse.py`, `test_scrape.py`. Touch only those files, `conftest.py` only if a shared helper must change, and this ticket. Keep every tag, attribute, class, nesting and field the parser reads. Replace all question text, choices, answers, votes, discussion, user names and explanations with invented PMLE-style text. Never copy or reword text from the old fixture or the real bank. Change no parser or step code. Update a test assertion only where it quotes old text.

- [x] Every listed fixture rewritten with invented content (`gate.html` too, if it holds site text beyond structure)
- [x] No sentence of the old fixtures survives (compare old and new text)
- [x] Test assertions that quoted old text updated
- [x] Full pytest suite passes

**Verify:**

- `python scripts/check.py` passes
- Pick 3 question stems from the old fixture (`git show HEAD:<path>`): `git grep -F` finds none in the tree

## Build notes

- Kept by necessity (parser or test reads them): page-count line, `Question #N`, `Answer X` spans, `Most Voted`, `login-modal`, classes and ids, button labels; gate.html shares no text with the old one.
- Rewrote site chrome too: modal text, vote title attribute, "Reader pick so far:" lead-in.
- Updated quoted text in `test_examtopics_parse.py` and `test_scrape.py`; no parser or step code changed.
- `git grep -F "Fixture stem one"` still hits the certsafari fixtures and tests (ticket 14 scope), not an examtopics stem.
- Files keep CRLF endings as before. `npm test` fails one import-steps CRLF assertion (template vs server.js), unrelated and untouched.
