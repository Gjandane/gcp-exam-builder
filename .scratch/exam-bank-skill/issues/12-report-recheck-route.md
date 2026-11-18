# 12: Report re-check route

Spec: [0001, Recheck route](../../../docs/specs/0001-exam-bank-skill.md#recheck-route), [Step 7: answers](../../../docs/specs/0001-exam-bank-skill.md#step-7-answers)

**What to build:** The user downloads the app's Reports tab as CSV into the reports folder and runs the recheck route. Each open Report's question gets a fresh blind answer that reads the user's note last. The row then carries a re-check time and a one-line note saying confirmed, changed, retired or user answer kept. The next export carries both to the app.

**Blocked by:** 01, 05

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** The route never reopens a main step. Auto-retire does not apply here. A `by: user` explanation is never rewritten. Question text and choices come back untouched. The user runs the live Verify step in a fresh session.

- [x] The batches command reads the newest CSV in the reports folder by modified time, by header name
- [x] A Report is pending by the spec's three conditions. Unknown and retired IDs are skipped and listed
- [x] The input is the answers shape plus a `report_notes` section the worker reads last
- [x] The recheck step file exists and follows the dispatch procedure
- [x] The answers worker file covers the re-check rules, or the route's step file adds them, without changing behaviour for step 7
- [x] Apply produces the four outcomes in the spec's table, with the `uncertain` change and the note prefix for each
- [x] `rechecked_at` is set on every outcome. `updated_at` moves only when answer or explanations changed
- [x] `recheck_note` is one line of plain text, at most 300 characters
- [x] A failed row stays active and is listed in `state.md`
- [x] The route ends by printing the export command and the import steps text

**Verify:**

- Run `pytest`. Tests cover each of the four outcomes, the pending filter, and a second run on the same reports file finding nothing
- Export after a fixture re-check. Columns 29 and 30 are filled on the re-checked row
- User, in a fresh session: put a Reports CSV with one open Report in the reports folder and run `/exam-bank pmle recheck`. The row's `rechecked_at` is later than the Report's `reported_at`

## Build notes

- Modules: added `recheck` (newest Reports CSV, open and pending filter); `RecheckTask` in `batches` subclasses `AnswersTask`, task `report_recheck`, no auto-retire.
- Interface: `eb.py batches|apply <exam> recheck`; the input adds `report_notes`, results use `step: recheck`; `apply` prints the export command and import steps once no Batch is left.
- New calls: `batches.configuration` calls `task.load` for tasks that read outside the bank; `state` lists failed recheck Batches and their question IDs under Notes.
- Mismatch: the worker's re-check rules sit in `workers/answers.md` behind the `report_notes` condition; step 7 text is unchanged.
- Not run: the live `/exam-bank pmle recheck` Verify step is the user's, in a fresh session.
