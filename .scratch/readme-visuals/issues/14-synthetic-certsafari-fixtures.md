# 14: Synthetic certsafari fixtures

Spec: [0001, Notes and License](../../../docs/specs/0001-exam-bank-skill.md#7-notes-and-license). Log: RV-D33; old ticket 08, decision 1.

**What to build:** The certsafari fixtures hold only invented questions, with the same page structure as before, so the public repo republishes no question-site content and every test still passes.

**Blocked by:** none

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Worktree. Files, under `.claude/skills/exam-bank/scripts/tests/fixtures/`: `certsafari/practice-questions.html` and its generator `certsafari/build_fixture.py`. Test that reads them: `test_certsafari_parse.py`. Touch only those files, `conftest.py` only if a shared helper must change, and this ticket. Keep every tag, attribute, class, nesting and field the parser reads. Replace all question text, choices, answers and explanations with invented PMLE-style text. If `build_fixture.py` generates the HTML, change the generator and regenerate. Never copy or reword text from the old fixture or the real bank. Change no parser or step code. Update a test assertion only where it quotes old text.

- [x] Fixture and generator rewritten with invented content
- [x] No sentence of the old fixture survives (compare old and new text)
- [x] Test assertions that quoted old text updated
- [x] Full pytest suite passes

**Verify:**

- `python scripts/check.py` passes
- Pick 3 question stems from the old fixture (`git show HEAD:<path>`): `git grep -F` finds none in the tree

## Build notes

- None.
