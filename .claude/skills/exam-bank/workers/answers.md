# Answers worker

Read the input file named in the prompt. Complete and write down the blind answer for every question before reading any of `source_answers`. Then, for each question:

1. Answer from the question and choices alone, before reading `source_answers`.
2. Read `source_answers`, then decide the answer. A question with no entry there has an empty `stored` and no sources.
3. Use your knowledge and WebSearch and WebFetch on Google Cloud documentation only. List in `refs` only pages fetched in this session.
4. Always pick an answer, confidence (`high`, `medium`, or `low`), and a one-line note. Return `unusable` with a reason only for a broken question.
5. If your answer equals `stored`, write explanations only for choices that lack one. If it differs or `stored` is empty, write every explanation except those marked `by: user`. Never rewrite a user Why line.
6. List in `why_conflicts` each choice whose user explanation contradicts your answer.

Each explanation is 1 to 3 sentences, starts with `Correct.` or `Incorrect.`, and names the Google Cloud fact that decides it. Include a documentation URL only if you fetched that page. Use plain text with line breaks and backticks around code. Outside backticks, use no HTML tags, Markdown links, heading lines, or bold markup.

Re-check (only when the input has `report_notes`; step `recheck`): read `report_notes` last, after your blind answer and `source_answers`. It maps each question ID to the user's note on a reported problem. Decide the answer on the evidence, never on the note alone. Rule 5 changes: when your answer equals `stored`, also rewrite any explanation the note shows to be wrong, except a `by: user` one. When it differs, write every explanation except `by: user` ones. Never change question text or choices. If the note points at a text problem, say so in `note`. Keep `note` and `reason` to plain text on one line, 250 characters at most. `why_conflicts` works as above.

Write one JSON file to the result path. Copy `batch_id` and `step` from the input and include one result per question, with its unchanged `id`:

```json
{"batch_id":"answers-0007","step":"answers","results":[
  {"id":"q_3fa9c21b07de","status":"ok","answer":["A"],"confidence":"medium","note":"The documentation supports A.","refs":["https://cloud.google.com/dataflow/docs/concepts/streaming-pipelines"],"explanations":{"A":"Correct. ...","B":"Incorrect. ..."},"why_conflicts":[]},
  {"id":"q_0b1c2d3e4f5a","status":"unusable","reason":"Choice B is cut off."}
]}
```

Read only the worker and input files; write only the assigned result file. Never read or write `bank.jsonl`. Reply with one line: `<batch_id> done`.
