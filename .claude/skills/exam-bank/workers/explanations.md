# Explanations worker

Read the input file named in the prompt. Each question carries its `answer`, the explanations it already has (`explanations`, with `by`), and `explanation_blocks`, which are undivided source explanations. For each question:

1. Treat `answer` as given. Never change it and never return one.
2. Write an explanation for every choice whose letter is not in `explanations`. Leave choices that already have one alone. Never return text for them.
3. Write each explanation for the answer as given, even when you doubt it. Use `explanation_blocks`, your knowledge, and WebSearch and WebFetch on Google Cloud documentation only. List in `refs` only pages fetched in this session.
4. If the given `answer` looks wrong, return status `doubt` with a one-line `reason`. Still write an explanation for every choice that lacks one, for the answer as given. Use `ok` otherwise.

Each explanation is 1 to 3 sentences, starts with `Correct.` for a choice in `answer` and `Incorrect.` for any other, and names the Google Cloud fact that decides it. Include a documentation URL only if you fetched that page. Use plain text with line breaks and backticks around code. Outside backticks, use no HTML tags, Markdown links, heading lines, or bold markup. The `reason` follows the same text rules and holds no URL outside Google Cloud documentation.

Write one JSON file to the result path. Copy `batch_id` and `step` from the input and include one result per question, with its unchanged `id`:

```json
{"batch_id":"explanations-0003","step":"explanations","results":[
  {"id":"q_3fa9c21b07de","status":"ok","explanations":{"A":"Correct. ...","B":"Incorrect. ..."},"refs":["https://cloud.google.com/dataflow/docs/concepts/streaming-pipelines"]},
  {"id":"q_0b1c2d3e4f5a","status":"doubt","reason":"Dataflow docs say B, not A.","explanations":{"B":"Incorrect. ..."},"refs":[]}
]}
```

Read only the worker and input files; write only the assigned result file. Never read or write `bank.jsonl`. Reply with one line: `<batch_id> done`.
