# Specs

Build-ready specs. Paths and naming: `docs/agents/context-docs.md`. Vocabulary: `GLOSSARY.md`. ADRs: `docs/adr/`.

| # | Spec | Covers |
|---|---|---|
| 0001 | [exam-bank skill](0001-exam-bank-skill.md) | The Claude Code skill that builds the **Question bank**: config, the 10 steps, the **Study guide** and **Report** re-check routes, state, workers, scripts, the CSV export, the skill-owned README parts |
| 0002 | [study app](0002-study-app.md) | The Apps Script app over the Google Sheet: sheet tabs, load and bank checks, Settings and home screens, **Review mode**, spaced repetition, the **Mock Test** with sampler, results and history, the app side of the **Report** re-check loop, Copy prompt, the server interface and its Node tests, the app-owned README parts |

Shared contract: the app reads the file the skill exports. Its columns, ID rules and answer letters are defined once, in [0001, CSV contract](0001-exam-bank-skill.md#csv-contract).
