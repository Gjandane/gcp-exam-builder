# Study guide

Run this route outside shared dispatch. One invocation writes one Subdomain chapter.

1. Run `python .claude/skills/exam-bank/scripts/eb.py study-guide-plan <exam> [<subdomain>] [redo]` with the remaining route arguments. It rebuilds `study_guide_state.md`. On a stop, report its reason and stop.
2. Spawn one Agent with the printed agent type, alias as `model`, and effort. Prompt: `Read <worker path> and follow it. Input: <input path>. Write the chapter to <chapter path>. Reply with one line: <subdomain> done.` Use the paths from the plan. Keep this same input for retries.
3. Run `python .claude/skills/exam-bank/scripts/eb.py study-guide-check <exam> <subdomain>`. On failure the script deletes the invalid chapter. Pass the error to a new subagent with the same type, alias, effort and paths. Repeat step 2 and the check up to two retries, three attempts total. After three failures, report the errors and stop. The Subdomain stays ready.
4. On a pass, report the chapter path and the script's status. The check rebuilds the index. Return to the router for its final state summary. Only scripts write `study_guide_state.md`.
