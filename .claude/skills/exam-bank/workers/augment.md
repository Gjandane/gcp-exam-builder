# Augment worker

Read the input file named in the prompt. It names one Subdomain (`subdomain.number`, `subdomain.title`) and `count`, the number of new questions to create. It also holds `examples` (full questions of this Subdomain or its Section), `existing_stems` (every stem already in this Subdomain), `choice_count_mix` (how many existing questions have each choice count) and `multi_select_share`.

Create exactly `count` new questions:

1. Each question tests a fact or scenario that no entry of `existing_stems` and no other new question tests.
2. Write scenario stems like the examples. Match the `choice_count_mix` and the `multi_select_share`. A multi-select stem says "Choose N" or "Select N", and `answer` then holds exactly N letters.
3. Use your knowledge and WebSearch and WebFetch on Google Cloud documentation only. Fetch at least one documentation page per question. List in `refs` only pages fetched in this session.
4. Give 2 to 6 choices, in text without a leading label. Letters follow the order: A, B, C and so on. `answer` holds sorted letters.
5. Write one explanation per choice. Each is 1 to 3 sentences, starts with `Correct.` or `Incorrect.`, and names the Google Cloud fact that decides it. Include a documentation URL only if you fetched that page. Use plain text with line breaks and backticks around code. Outside backticks, use no HTML tags, Markdown links, heading lines, or bold markup.
6. `subdomain` is the input's Subdomain number. `derived_from` lists the example IDs whose style or topic the question follows, at least one when `examples` is not empty. Never invent an ID.
7. `confidence` is `high`, `medium` or `low`. `note` is one line.
8. Return `status: unusable` with a `reason` only for a question you cannot finish.

Write one JSON file to the result path. Copy `batch_id` and `step` from the input. Give each question a `key` that is unique in the file, such as `n1`, `n2`:

```json
{"batch_id":"augment-0001","step":"augment","results":[
  {"key":"n1","status":"ok","question":"...","choices":[{"text":"...","explanation":"Correct. ..."},{"text":"...","explanation":"Incorrect. ..."}],
   "answer":["A"],"subdomain":"5.1","derived_from":["q_3fa9c21b07de"],"confidence":"medium","note":"One line.",
   "refs":["https://cloud.google.com/vertex-ai/docs/pipelines/introduction"]},
  {"key":"n2","status":"unusable","reason":"No fact left to test."}
]}
```

Read only the worker and input files; write only the assigned result file. Never read or write `bank.jsonl`. Reply with one line: `<batch_id> done`.
