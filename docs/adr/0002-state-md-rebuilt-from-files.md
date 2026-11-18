# A script rebuilds state.md from the files

The exam-bank skill's `state.md` is output, not a record anyone edits. A Python script rebuilds it on every invocation from the data on disk: per-source JSONL files, `bank.jsonl`, each step's `batches/<step>/manifest.json` and the Batch result files. The few facts the data cannot show (augmentation opt-in, skipped steps, a source waiting on the user) live in `state.json`, which only scripts write.

We first gave state.md to the haiku bookkeeping task. We dropped that because a session that dies mid-wave leaves a hand-edited state wrong, and the next session would trust it. A step is now done when the script finds no pending work, so resume needs nothing from the dead session.

## Consequences

- Never edit `state.md` by hand or by LLM. The next run overwrites it.
- Step status comes from the data. Adding questions later reopens merge and every later step with pending rows.
- The manifest is append-only. A Batch is pending when its entry has no valid result file.
- Results apply by question ID, so applying one twice changes nothing.
- No LLM keeps any state file. Scripts create the folders and rebuild `study_guide_state.md` the same way; the haiku bookkeeping task is gone.
