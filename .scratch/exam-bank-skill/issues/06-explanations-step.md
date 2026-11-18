# 06: Explanations step

Spec: [0001, Step 8: explanations](../../../docs/specs/0001-exam-bank-skill.md#step-8-explanations), [Explanation style](../../../docs/specs/0001-exam-bank-skill.md#explanation-style)

**What to build:** The user runs the explanations step and every choice of every active row ends up with an explanation. A subagent that thinks the given answer is wrong returns `doubt`, which sends an unchecked row back to the answers step once.

**Blocked by:** 01, 05

**Status:** resolved

**Model tier:** standard
**Effort:** low
**Where:** cli
**Constraints:** The worker leaves the answer as given. Reuse the answers validation code. The user runs the live Verify step in a fresh session.

- [x] A row is pending when it is not pending for answers and a choice lacks an explanation
- [x] The input is the answers shape with the answer and existing explanations inside each question
- [x] The worker file holds the worker rules and the explanation style
- [x] Validation runs the answers checks that apply, plus a reason on `doubt`
- [x] `ok` applies explanations with `explanation_by: llm` per written choice, sets the row value and `updated_at`
- [x] `doubt` on an unchecked row sets `uncertain` TRUE and discards the returned explanations
- [x] `doubt` on a checked row applies the explanations and appends the reason to the note
- [x] The explanations step file exists and follows the dispatch procedure
- [x] One fixture input file for a manual worker run ships with the tests

**Verify:**

- Run `pytest`. Apply tests for `ok`, `doubt` on an unchecked row and `doubt` on a checked row pass
- After a `doubt` on an unchecked row, run the state command. Answers is the current step
- User, in a fresh session: run `/exam-bank pmle explanations`, then the export step. Export does not refuse

## Build notes

- Added `ExplanationsTask` to `batches.py` and `validate.explanations`; no module added or removed.
- `validate.explanation_error` now holds the refs, key, cell-text and doc-link checks that `validate.answers` and `validate.explanations` share; `batches.explanation_by` and `answers_pending` are shared by both tasks.
- `apply` passes the bank row to the explanations validator, as for answers. The worker's `doubt` reason is checked as cell text and doc links, then appended to `answer_note` as `Explanations doubt: <reason>`.
- Worker input is one `questions` list (no `source_answers`); a returned text for a choice that already has one is ignored.
- Unrun: `/exam-bank pmle explanations` then export in a fresh session (needs the user).
