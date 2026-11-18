# 11: Augment step

Spec: [0001, Step 9: augment](../../../docs/specs/0001-exam-bank-skill.md#step-9-augment)

**What to build:** The user runs the augment step, sees a gap table per Subdomain and answers yes or no once. On yes, subagents create new questions for thin Subdomains, a second blind subagent checks each answer, and only questions where both agree enter the Question bank with Lineage `created`. On no, the step is skipped.

**Blocked by:** 01, 05, 07

**Status:** resolved

**Model tier:** standard
**Effort:** high
**Where:** cli
**Constraints:** The plan is fixed once written. Drops are not refilled, and a reopen of earlier steps never reopens augment. A verify session sees no creator answer and no creator explanations, and its own explanations are discarded. The user runs the live Verify step in a fresh session.

- [x] The plan command prints the gap table with the total against the per-run cap
- [x] The gap rule matches the spec: target by Section weight, the per-Subdomain floor, and largest-remainder scaling under the cap
- [x] The main session asks once and the answer is recorded in the state file. No marks the step skipped. A forced run plans new gaps
- [x] A create Batch is one Subdomain with up to `batch_size` questions
- [x] The create input holds the example rows by the spec's pick rule, seeded by Batch id, every existing stem, and the choice-count mix and multi-select share
- [x] The worker file holds the create rules
- [x] Create validation runs the answers checks plus choice count, Subdomain, `derived_from` and at least one ref
- [x] Each valid create result gets one verify entry on the answers worker with an empty source-answers section
- [x] A question is kept only when the verify answer equals the creator's and verify confidence is not low. Kept confidence is the lower of the two
- [x] Drops are counted in `state.md`
- [x] Kept questions go to the created source file as complete rows, and merge runs on that file
- [x] The augment step file exists, covers the opt-in question and follows the dispatch procedure
- [x] One fixture input file for a manual create worker run ships with the tests

**Verify:**

- Run `pytest`. Gap rule tests cover rounding, the floor and the cap. Keep and drop tests cover a matching answer, a differing answer and low confidence
- Run the plan command on a fixture bank. The table's planned total does not exceed the cap
- User, in a fresh session: run `/exam-bank pmle augment` and answer yes. Afterwards the bank holds `created` rows with `derived_from` set and `uncertain` FALSE, and export does not refuse
- Run the state command again. Augment is done and no earlier step reopened

## Comments

- Verify results: `pytest` passes (gap rule rounding, floor and cap; keep and drop for a matching answer, a differing answer and low confidence; create validation; whole create, verify and apply flow). The plan command on a fixture bank prints a total within the cap, and export accepts a kept row.
- Unrun: the live `/exam-bank pmle augment` run in a fresh session (needs the user and real subagents), and its follow-up state check. `tests/fixtures/workers/augment.in.json` is for a manual create worker run.

## Build notes

- Added `augment.py` (gap rule, plan, create and verify Batches, keep or drop, merge of `created.jsonl`); `eb.py` gains `augment-plan [yes|no]`; `batches.run/apply` hand step `augment` to it.
- `augment` calls `merge.merge_records` on `created.jsonl` alone and records only that file's hash in `merged`, so unmerged scrape files stay untouched.
- Manifest `items` for create entries are `{subdomain, count}`. Verify is one entry per valid created question (item `<create batch id>#<key>`), so up to 100 single-question answer_filling sessions at the default cap; spec wording allows one per create file instead. All entries use `step: augment`.
- `state.py` prints `augment drops: N` from `log.jsonl` instead of one note per drop. The answers worker treats a question missing from `source_answers` as empty.
- Create results with too few valid questions requeue only the missing count as a new create Batch; an exhausted entry restarts at attempt 1 on the next `batches` run.

