# 04: Dispatch with tag

Spec: [0001, Dispatch](../../../docs/specs/0001-exam-bank-skill.md#dispatch), [Step 6: tag](../../../docs/specs/0001-exam-bank-skill.md#step-6-tag), [Workers](../../../docs/specs/0001-exam-bank-skill.md#workers). ADR 0002.

**What to build:** The user runs the tag step and every active row without a Subdomain gets one, set by subagents working in Batches. This ticket builds the shared fan-out that five steps and the re-check route reuse: forming Batches, the append-only manifest, validating and applying result files, retries and auto-retire. Tag is its first user.

**Blocked by:** 01, 03

**Status:** resolved

**Model tier:** heavy
**Effort:** high
**Where:** cli
**Constraints:** No subagent reads or writes the bank file. A manifest entry is never edited. Results apply by question ID, so a second apply changes nothing. Neither agent definition sets a model, an effort or the Agent tool. The dispatch procedure must stay step-neutral, since tickets 05, 06, 10, 11 and 12 build on it. The user runs the live Verify steps in a fresh session.

- [x] The batches command forms Batches from pending work, appends manifest entries, writes one input file each and prints the dispatch list with `max_parallel`
- [x] Batch size and parallelism come from the models config, per task over defaults, with the clamp at 20
- [x] The apply command validates new result files, applies valid questions, requeues the rest and prints the next list
- [x] A missing or invalid result file requeues as a new entry with the next attempt number. After attempt 3 the entry is failed and its questions stay pending
- [x] A partial result applies its valid questions and requeues only the rejected ones
- [x] Auto-retire fires only when two failed entries with parsed result files rejected the same question. An entry with no result file never counts
- [x] The dispatch procedure file holds the spec's four-step loop and the worker prompt line
- [x] Both agent definitions exist with the spec's tool lists
- [x] The tag worker file holds the tag rules and the shared frame
- [x] Tag input carries the Section and Subdomain list with hints, and no answers
- [x] Tag validation and apply follow the spec, including `unusable` retiring the row and `updated_at` staying put
- [x] Per-step Batch counts and failed Batch ids show in `state.md`
- [x] The tag step file exists and follows the dispatch procedure
- [x] One fixture input file for a manual tag worker run ships with the tests
- [x] Confirm-at-build 4 and 6 disposition recorded in the ticket comments: local dispatch and permission contracts checked; Claude Code runtime verification waived by the user

**Verify:**

- Run `pytest`. Batch forming, manifest, retry, partial result, attempt-3, auto-retire and tag apply tests on hand-written good and bad result files pass
- Apply the same good result file twice. The bank file is byte-identical after the second apply
- User, in a fresh session with the permission block pasted: run `/exam-bank pmle tag` on a bank with untagged rows. Subagents run without a permission prompt, and afterwards no active row has an empty Subdomain
- User: open the session transcript and check that each Agent call passed the agent type, alias and effort from the dispatch list

## Comments

- 2026-11-17: User explicitly waived Claude Code live checks for this build. This supersedes the fresh-session constraint and the two live Verify steps; runtime behavior is not claimed as verified.
- Confirm-at-build 4: CLI tests verify the dispatch list's agent type, alias and effort, including task overrides. The shared procedure passes them as `subagent_type`, `model` and `effort`; both custom definitions omit model and effort. Claude Code's actual per-call overrides and transcript were not checked, per waiver.
- Confirm-at-build 6: Local checks confirm setup's permission block exactly matches the spec, both agent tool lists match, and neither agent exposes Agent. Background permission-prompt behavior was not checked, per waiver.
- Verify 1: `pytest -q` passed, 147 tests. Batch formation, immutable manifest entries, partial apply, retries, attempt-3 exhaustion, auto-retirement, resume and write-failure recovery covered with good and bad result files.
- Verify 2: The repeat-apply test was run separately after the full suite; the bank remained byte-identical after the second apply.
- Verify 3 and 4: Waived by user. Local CLI tests cover complete tagging, preserving completed worker files, dispatch metadata and emitted-wave limits. Agent definitions, fixture JSON and permissions also passed local contract checks.
- Review: Standards and Spec reviewers report no remaining findings after fixes for resume, retirement evidence, logging recovery and wave tracking. Implementation commit: `5785cd0`.

## Build notes

- Added `batches` and `validate` modules; `eb.py batches <exam> <step>` and `apply` now support tag through a task adapter.
- Shared dispatch owns forming, retry, idempotent apply and retirement; the tag adapter owns pending rows, input and row changes.
- New calls: entry point to `batches.run`/`apply`, state to `batches.counts`, and dispatch to result validators.
- `state.json` adds `dispatch` application receipts and `dispatch_waves` emitted IDs for replay and resume; these bookkeeping keys are absent from the spec's example. Context docs left unchanged.
- Added both agents, shared procedure, tag step/worker and the manual worker fixture; Claude live verification waived as recorded above.
