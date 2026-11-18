# LLM-scrape

Read `.claude/skills/exam-bank/dispatch.md` and follow its procedure with the selected exam and step `llm-scrape`.

`eb.py batches` first runs `fetch`: a script downloads each enabled page, so no subagent needs a web tool. Report the fetch lines, listing every page that shows `failed: <reason>`, then the dispatch counts, failed Batch ids and dropped questions. A failed page does not stop the step. Tell the user the questions of a failed page can go in `given/`. Done when every enabled page has a valid result or a `failed` record.
