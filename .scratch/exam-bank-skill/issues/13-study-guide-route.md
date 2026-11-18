# 13: Study guide route

Spec: [0001, Study guide route](../../../docs/specs/0001-exam-bank-skill.md#study-guide-route), [Doc host rule](../../../docs/specs/0001-exam-bank-skill.md#doc-host-rule)

**What to build:** The user runs the study-guide route and gets one Study guide chapter for one Subdomain per run, written by a subagent from that Subdomain's questions. A script checks the chapter and an index file lists every Subdomain as ready, blocked, done or stale.

**Blocked by:** 01, 06

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** The route sits outside the shared dispatch. Question and choice text is never copied into a chapter. A script rebuilds the index on every run and nothing else writes it. The user runs the live Verify step in a fresh session.

- [x] The plan command rebuilds the index and picks the Subdomain: the first ready one, or the named one
- [x] Naming a blocked Subdomain stops with the reason. Naming one with a chapter stops unless `redo` is given
- [x] A Subdomain is blocked while it has rows pending for tag, answers or explanations
- [x] The input file holds the full active ID list and each fed row with marks on Uncertain answer and low-confidence rows
- [x] Over the question cap the script takes a seeded sample with non-`created` rows first
- [x] The worker file holds the chapter rules: front matter, the six headings in order, length, paraphrase, no claim resting only on marked rows
- [x] The check command rejects each case the spec lists, including a 12-word run shared with an input stem or choice
- [x] An invalid chapter is deleted and the subagent runs again, up to two retries
- [x] The chapter path uses the spec's title slug
- [x] A chapter is stale when the active ID list changed or a row was updated after it was written
- [x] The index lines carry status, question counts and the command to run
- [x] The study-guide step file exists and holds the route's four-step procedure
- [x] One fixture input file for a manual worker run ships with the tests

**Verify:**

- Run `pytest`. The check passes a good fixture chapter and rejects a bad one for each rule. Stale and blocked tests pass
- Run the plan command on a bank with pending answers in one Subdomain. The index shows it blocked with the count
- User, in a fresh session: run `/exam-bank pmle study-guide`. A chapter file appears, the check passes, and the index shows it done
- Edit a fed question's `given` block, rerun intake, merge and the later steps, then the plan command. The chapter shows stale

## Build notes

- Added study_guide module; eb.py now routes study-guide-plan and study-guide-check outside shared dispatch.
- Added four-step route, chapter worker, validator fixtures and manual worker input; no bank schema or Interface names changed.
- Verification: 366 pytest tests passed, compileall passed, Standards and Spec review findings fixed.
- Fresh parallel Claude session in isolated fixture bank passed blocked count, generated chapter, two deletion/retry cycles, done index and given-edit stale check.
- Commit a7808d6. Existing PMLE bank remains unmodified; it has 27 untagged rows and needs tag before this route can write a chapter.
