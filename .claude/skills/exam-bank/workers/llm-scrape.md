# LLM-scrape worker

Read the input file named in the prompt. It names one saved page: `source`, `url` and `txt_path`. Read the text file at `txt_path`. You have no web tool and never fetch anything.

Extract the practice questions on that page:

- Copy the question, every choice and every explanation verbatim from the text. Leave typos, odd spacing and odd punctuation as they are. Never reword, fix or merge text. A script rejects any text it cannot find in the page.
- Write each choice without its leading label (`A.`, `B)`). List the choices in page order. Letters follow that order: A, B, C and so on.
- `n` is the question number the page prints. When the page prints none, count the questions from 1 in page order.
- Record `answer` only when the page ties the answer clearly to that question. Otherwise use `[]`. Never work out an answer yourself.
- Explanations: when the page gives one per choice, use `{"A": "...", "B": "..."}` keyed by letter. When it gives one undivided explanation, use `{"block": "..."}`. When it gives none, use `{}`.
- `subdomain_label` is the label text the page prints for the question's topic, else `""`.
- Text is plain text with line breaks and backticks around code. No HTML, no Markdown.
- Return `skipped` with a one-line `reason` for a question that needs an image, or has under 2 or over 6 choices.
- If the input has an `only` list, return results only for those question numbers.

Write one JSON result file to the result path named in the prompt. Copy `batch_id` and `step` from the input. Shape:

```json
{"batch_id": "llm-scrape-0002", "step": "llm-scrape", "results": [
  {"n": 7, "status": "ok", "question": "...", "choices": ["...", "..."],
   "answer": ["B"], "explanations": {"A": "...", "B": "..."}, "subdomain_label": ""},
  {"n": 8, "status": "ok", "question": "...", "choices": ["...", "..."],
   "answer": [], "explanations": {"block": "..."}, "subdomain_label": ""},
  {"n": 9, "status": "skipped", "reason": "Needs an image."}
]}
```

Read only the worker file, the input file and the text file. Write only the assigned result file. Never read or write `bank.jsonl`. Reply with one line: `<batch_id> done`.
