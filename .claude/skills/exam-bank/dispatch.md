# Dispatch

Use the exam and step selected by the calling step file.

1. Run `python .claude/skills/exam-bank/scripts/eb.py batches <exam> <step>`. It forms Batches, appends manifest entries, writes input files, and prints the dispatch list and `max_parallel`. Each list item gives the Batch id, input path, result path, worker file, agent type, alias, and effort.
2. Spawn the first `max_parallel` Batches as Agent calls in one message. If the list is empty, continue to step 3 to apply any completed files recovered from a previous session. Pass each item's agent type as `subagent_type`, alias as `model`, and effort as `effort`. Fill its paths and Batch id into this prompt exactly:
   `Read <worker file> and follow it. Input: <input path>. Write your result to <result path>. Reply with one line: <batch_id> done.`
3. Wait for the whole wave, then run `python .claude/skills/exam-bank/scripts/eb.py apply <exam> <step>`. It validates new result files, applies valid questions, requeues rejected or missing results, and prints the next dispatch list.
4. Repeat steps 2 and 3 until `apply` prints an empty list. Report its counts, including failed Batch ids. Stop this step even if failed Batches leave questions pending. A later invocation retries them.

Workers read their worker file and input file and write only their assigned result file. No subagent reads or writes `bank.jsonl`. Scripts own the bank, manifest, and state files. Leave retries and retirement to `apply`.
