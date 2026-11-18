# Explanations

Read `.claude/skills/exam-bank/dispatch.md` and follow its procedure with the selected exam and step `explanations`.

The script selects active rows that are not pending for answers and have a choice without an explanation. Report dispatch counts and failed Batch IDs. A `doubt` on an unchecked row sends that row back to answers once: if the state command then names `answers` as the current step, tell the user to run `/exam-bank <exam> answers`, then explanations again. Explanations is done when every choice of every active row has an explanation; failed Batches may leave work for a later invocation.
