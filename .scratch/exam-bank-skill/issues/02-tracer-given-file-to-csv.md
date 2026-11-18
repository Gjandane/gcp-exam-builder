# 02: Tracer: given file to CSV

Spec: [0001, Step 4: intake](../../../docs/specs/0001-exam-bank-skill.md#step-4-intake), [Step 5: merge](../../../docs/specs/0001-exam-bank-skill.md#step-5-merge), [Step 10: export](../../../docs/specs/0001-exam-bank-skill.md#step-10-export), [Bank data](../../../docs/specs/0001-exam-bank-skill.md#bank-data), [CSV contract](../../../docs/specs/0001-exam-bank-skill.md#csv-contract). ADR 0001.

**What to build:** A user writes fully answered questions in a `given` file, runs intake, merge and export by script, and gets the 30-column CSV and `bank_meta.json` for the study app. No LLM takes part. This is the first path through every layer of the Question bank: the given format, the per-source file, ID assignment, the bank file and the export.

Merge here covers only what the tracer needs: new rows, a `given` key update in place, and reattaching a record the bank already holds. Ticket 07 adds the rest.

**Blocked by:** 01

**Status:** resolved

**Model tier:** heavy
**Effort:** medium
**Where:** cli
**Constraints:** ADR 0001 freezes the ID algorithm at the first merge, so the golden vectors written here are permanent. The CSV contract binds spec 0002. Change neither without the user. Only merge writes the bank file in this ticket, through a temp file and a rename.

- [x] `norm` and the question ID follow the spec's ID rules, with golden vectors that include a reordered-choices pair producing one ID
- [x] Intake parses the shipped given example into the per-source file, with lineage, ticks, Subdomain, `Why:` lines and the `unsure` mark
- [x] Intake skips and logs each bad block by file and line: choice count out of range, no question text, duplicate key, image
- [x] Intake treats lines inside a code fence as text
- [x] A Subdomain number missing from the exam config is dropped with a warning
- [x] Merge creates one row per new question with the ID as computed, and a rerun on unchanged files changes nothing
- [x] An edited `given` block updates its row in place and keeps the ID
- [x] Merge records each source file's hash in the state file, and writes `schema_version`, `exam` and `guide_version` to `bank_meta.json`
- [x] The given example template ships with exactly the content the spec gives
- [x] Export refuses when an active row lacks an answer, a Subdomain or an explanation for a filled choice. It prints up to 20 IDs with the missing part and writes nothing
- [x] Export writes the CSV in the spec's file format with the exact header row, and rewrites `bank_meta.json`
- [x] Export prints the counts, the `section_weights` line and the import steps text
- [x] The import steps template ships with the spec's wording

**Verify:**

- Run `pytest`. The ID golden vectors, the intake fixture test, the merge rerun test and the byte-for-byte export golden test pass
- Copy both templates into the config folder, put a file of fully answered questions under the PMLE `given` folder, run intake, merge and export through the entry point. The CSV appears and its first line equals the spec's header row
- Run merge twice. The bank file is byte-identical after the second run
- Remove the ticks from one question and rerun. Export refuses and names that ID

## Build notes

- Modules: added `ids`, `intake`, `merge`, `export`, and `store` (paths, exam config, JSON I/O, atomic write, log), which the spec's Scripts list lacks.
- Interface: each step is `run(root, exam, now)` returning its text; `store.Stop` exits 1; extra arguments are refused, so `merge [file]` is unbuilt.
- Mismatch, layout: ignore rule is `/exam-bank/` (the unanchored rule hid the skill folder, first tracked in `30c3736`); cache ignores and `.gitattributes` (`-text` on test fixtures) added.
- Mismatch, merge, for ticket 07: runs ahead of tracer scope (dedupe attach, stored answer without trust rules, Uncertain rules 1, 2, 4). Only a given block that brought the row rewrites its text, narrower than Step 5 rule 1, which conflicts with "stored order of the first source" in Answer letters. `_remap` drops letters of edited choices without a warning.
- Pinned by tests, unstated in spec: fence lines and language tag feed the ID; a non-`Why:` line under a choice extends its text; export also refuses a Subdomain missing from the config, and checks no other app guarantee.
