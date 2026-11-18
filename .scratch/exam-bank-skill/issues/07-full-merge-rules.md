# 07: Full merge rules

Spec: [0001, Step 5: merge](../../../docs/specs/0001-exam-bank-skill.md#step-5-merge), [ID rules](../../../docs/specs/0001-exam-bank-skill.md#id-rules), [Answer letters](../../../docs/specs/0001-exam-bank-skill.md#answer-letters). ADR 0001.

**What to build:** The same question arriving from several sources becomes one row with every source attached. Merge remaps each source's answer letters into the stored choice order, picks the stored answer and explanations, raises Uncertain answer by the four rules, and handles edits to a `given` block and a new guide version. Ticket 02 built new rows only.

**Blocked by:** 01, 02

**Status:** resolved

**Model tier:** heavy
**Effort:** medium
**Where:** cli
**Constraints:** ADR 0001: never recompute or repair a stored ID. Same input gives the same output. Merge never sets `uncertain` FALSE on an existing row. Rows are never deleted.

- [x] Sources are read in the spec's order: `given`, Curated sites in config order, LLM-scrape sources in config order, `created`
- [x] Dedupe compares an incoming hash with every stored ID and every row's current-text hash
- [x] A record already attached refreshes only when its hash still matches. A key match with a different hash logs a warning and goes through dedupe
- [x] A matched record is attached with its letters remapped into the stored choice order. A matched `created` record is dropped and logged
- [x] A `created` record with no match brings its whole row along
- [x] A source Subdomain label is kept only when its number and normalized title both match one config entry. A valid `given` line wins. Anything else leaves the tag empty
- [x] The stored answer follows the spec's precedence: ticks without `unsure`, then ticks with `unsure`, the first trusted source, the first untrusted source. Rows with an LLM answer are left alone except by ticks without `unsure`
- [x] Ticks that change the stored answer clear the LLM-written explanations
- [x] Stored explanations come from `Why:` lines, else the first source with one explanation per choice, and never overwrite LLM text
- [x] All four Uncertain answer rules fire as the spec states, with `given` and `created` counted as trusted
- [x] The check mark is cleared when a new or changed source answer differs from the stored answer
- [x] A changed `given` question or choice clears the LLM answer, the LLM explanations and the check mark. User content and the Subdomain tag stay
- [x] A removed `given` block leaves its row and logs the missing key
- [x] A changed guide version clears non-user tags, reruns the label match, clears stale user tags with a warning and writes the new version
- [x] The CSV `sources`, `source_urls` and `source_answers` cells come out right for a multi-source row, community answer line included

**Verify:**

- Run `pytest`. Fixture source files merge into the expected bank file, and the rerun test leaves it byte-identical
- Tests for letter remap, each Uncertain answer rule, the `given` edit, the removed block and the guide version change pass
- Merge two fixture sources that hold the same question with choices in a different order. The bank has one row with two source records and the second source's letters remapped
- Change `guide_version` in the exam config, run the state command. Merge is the current step

## Build notes

- Modules: extended `merge`; added multi-source golden fixtures and merge regression tests; CLI names and cross-module calls unchanged.
- State: `given_texts` in script-owned `state.json` preserves each given key's previous text/order, so edits to later copies apply without rerun drift; absent from the spec's state example.
- Verification: 116 pytest tests pass, including 52 merge tests; CLI fixture merge confirms remapping and byte-identical reruns; a guide-version change routes state to merge.
- Review: consolidated source ordering; fixed file moves incorrectly clearing checks on unchanged given blocks; standards and spec review findings resolved.
- Existing scope gap: optional `merge [file]` remains unbuilt; this ticket's criteria use all-source merge. No Claude Code live checks required or performed.
