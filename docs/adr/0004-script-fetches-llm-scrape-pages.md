# A script fetches the page; the LLM only extracts

In the `llm-scrape` step a Python script downloads each source page and saves its text under `raw/<source>/`. The subagent reads that file and extracts the questions. The script then rejects any question whose stem or choices do not appear in the saved text.

The simpler design was to let the subagent fetch the page with WebFetch. We dropped it because WebFetch answers through a small model and can paraphrase. Duplicates are found by an exact hash of the normalized question text and choices (ADR 0001), so a reworded stem would enter the bank as a new question and nothing could detect it. Letting the subagent run curl gives exact text but needs network permission per subagent and still leaves no check on what it wrote.

## Consequences

- An `llm-scrape` worker needs no web tool. It reads one file and writes one result file.
- Only static pages work. A dynamic page, login wall or bot block marks that page `failed` with a reason; the step still finishes.
- The saved page is the evidence for every scraped question from that source.
- The LLM may not fix typos or reword a stem. Text that differs from the page is rejected.
