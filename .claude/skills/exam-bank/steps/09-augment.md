# Augment

Opt-in. The plan is fixed once written: drops are not refilled and a reopen of earlier steps never reopens this step.

1. Run `python .claude/skills/exam-bank/scripts/eb.py augment-plan <exam>`. It prints the gap table, the total planned against `max_created_per_run`, and `opt_in: unset|yes|no`. A line saying a plan is open means Batches are unfinished: skip to step 4.
2. Ask the user once, when `opt_in` is `unset` or this step was named in the command: "Create the planned questions? Each is checked by a second blind subagent, and only questions both agree on enter the bank." Show the table with the question.
3. Record the answer with `eb.py augment-plan <exam> yes` or `eb.py augment-plan <exam> no`. On no, report the step as skipped and stop. On yes, the script writes the create Batches.
4. Read `.claude/skills/exam-bank/dispatch.md` and follow its procedure with the selected exam and step `augment`. Create Batches run first. Each valid created question then gets its own verify Batch, so `apply` prints new Batches after the first wave. Keep repeating until it prints an empty list.

Report the plan total, `Questions: kept N, dropped M`, and failed Batch ids. Drops show in `state.md`. A failed Batch stays open for a later invocation. Done when every create and verify Batch has a valid result and the kept questions are merged.
