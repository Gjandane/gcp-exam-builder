# Recheck

Read `.claude/skills/exam-bank/dispatch.md` and follow its procedure with the selected exam and step `recheck`.

Before it runs, the user downloaded the app's Reports tab as CSV into `exam-bank/<exam>/reports/`. The batches command reads the newest `*.csv` there by modified time and prints its name, then one `skipped` line per open Report whose question is unknown or retired. If it stops for a missing CSV or column, print its message and stop.

The worker is `workers/answers.md`. Its input adds `report_notes`, and its re-check rules apply. This route never reopens a main step. Auto-retire does not apply: a failed Batch leaves its rows `active` and their Reports open, and `state.md` lists them. A `by: user` explanation is never rewritten.

Report dispatch counts, failed Batch IDs and the skipped lines. When `apply` prints an empty list, it ends with the export command and the import steps. Print that text as it is.
