# Tag worker

Read the input file named in the prompt. It contains the full Section and Subdomain title list with hints, and each question's `id`, `question`, `choices`, and `source_labels`. Treat source labels as hints.

For each question:

- Pick the Subdomain of the decision the stem's final ask calls for, over the scenario background. Still tied, pick the title or hint naming the product in the correct-looking choices. Return the runner-up as optional `alt`.
- Always pick the nearest Subdomain. Use `low` confidence when unsure. Confidence is `high`, `medium`, or `low`.
- Return `unusable` only for a broken question, such as garbled text or missing choices, with a nonempty `reason`.

Write one JSON result file to the result path named in the prompt. Copy `batch_id` and `step` from the input. Return one result per input question, using its unchanged `id`. An `ok` result has a configured `subdomain` and `confidence`; optional `alt` must be a different configured Subdomain. Example shape:

```json
{"batch_id":"tag-0003","step":"tag","results":[
  {"id":"q_3fa9c21b07de","status":"ok","subdomain":"5.1","confidence":"medium","alt":"5.2"},
  {"id":"q_0b1c2d3e4f5a","status":"unusable","reason":"Stem cut off."}
]}
```

Read only the worker and input files; write only the assigned result file. Never read or write `bank.jsonl`. Reply with one line: `<batch_id> done`.
