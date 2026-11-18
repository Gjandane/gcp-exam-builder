# 05: Answers step

Spec: [0001, Step 7: answers](../../../docs/specs/0001-exam-bank-skill.md#step-7-answers), [Explanation style](../../../docs/specs/0001-exam-bank-skill.md#explanation-style), [Doc host rule](../../../docs/specs/0001-exam-bank-skill.md#doc-host-rule), [Cell text rule](../../../docs/specs/0001-exam-bank-skill.md#cell-text-rule)

**What to build:** The user runs the answers step and every active row with a missing answer or an Uncertain answer gets a checked answer, a confidence, a note and doc references. Each subagent answers blind first, then reads the source answers. User ticks and user `Why:` lines survive.

**Blocked by:** 01, 04

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** The input keeps existing explanations apart from the choices, so the blind pass cannot see them. A `by: user` explanation is never rewritten. The input and result shapes are reused by augment verify and the re-check route, so keep them as the spec gives them. The user runs the live Verify step in a fresh session.

- [x] The answers input file has the spec's shape, with source answers, explanations and explanation blocks in their own section
- [x] The worker file holds the six worker rules and the explanation style
- [x] Validation covers every check in the spec: letters within the choices, the choose-N count, confidence, full explanation coverage after apply, `why_conflicts` letters, cell text, doc host, a reason on `unusable`
- [x] The cell text check and the doc host check are shared code other steps can call
- [x] Apply on `ok` sets the answer fields, the check mark and `updated_at`
- [x] Low confidence on a row with no stored answer sets `uncertain` TRUE. A row that had it keeps it
- [x] On a row with user ticks and no `unsure`, the ticks stay. A differing LLM answer sets `uncertain` TRUE, goes into the note, and the returned explanations are discarded
- [x] With `unsure` true the LLM answer replaces the ticks
- [x] Returned text for a `by: user` choice is discarded without rejecting the question
- [x] A non-empty `why_conflicts` keeps the user text, sets `uncertain` TRUE and extends the note
- [x] `unusable` retires the row and logs the reason
- [x] The answers step file exists and follows the dispatch procedure
- [x] One fixture input file for a manual worker run ships with the tests
- [x] Confirm-at-build 7 is settled and recorded in the ticket comments: whether Google Cloud docs answer from `docs.cloud.google.com`, which decides the second WebFetch permission line

**Verify:**

- Run `pytest`. Validation and apply tests on hand-written result files pass, including the user-ticks, `unsure`, `why_conflicts` and choose-N cases
- Run the batches command on a bank with one unanswered row and one checked row. Only the unanswered row is in a Batch
- User, in a fresh session: run `/exam-bank pmle answers`. Afterwards no active row is pending for answers, and each `answer_refs` URL is on a Google Cloud docs host

## Comments

- 2026-11-17: Confirm-at-build 7: [Google Cloud documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform) responds on `docs.cloud.google.com`. Keep the second WebFetch permission line.
- 2026-11-17: User waived the Claude Code live check. An isolated CLI run used a hand-written result and a fetched Google Cloud docs reference; no active row remained pending and the user explanation survived. Claude worker execution was not tested.
- `pytest -q`: 198 passed. A separate Batch test confirmed only the unanswered row was selected.
- Review: standards and spec findings fixed. Implementation commit: `dbcb93b`.

## Build notes

- Added the answers dispatch adapter, step, worker and manual input fixture.
- Shared `validate.cell_text`, `validate.doc_host` and answer validation support later steps.
- Dispatch validation now supplies the bank row to the answers adapter.
