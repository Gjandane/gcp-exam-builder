---
name: exam-bank
description: Build and export a Question bank for one exam, one step per run.
disable-model-invocation: true
argument-hint: <exam> [step] [args]
---

1. Read `$ARGUMENTS`. If no exam was supplied, print these forms and stop:
   - `/exam-bank <exam>`
   - `/exam-bank <exam> <step>`
   - `/exam-bank <exam> study-guide [<subdomain>] [redo]`
   - `/exam-bank <exam> recheck`
2. Run `python .claude/skills/exam-bank/scripts/eb.py state <exam> [step]` with the supplied exam and optional step. If it fails, report the error and stop.
3. Read only the step file named by that command, using the Read tool, and follow it. Pass any remaining arguments to that step.
4. Run `python .claude/skills/exam-bank/scripts/eb.py state <exam>`. Print its summary and next command. Stop.
