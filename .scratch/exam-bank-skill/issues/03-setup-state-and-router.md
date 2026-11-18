# 03: Setup, state and router

Spec: [0001, Invocation and routing](../../../docs/specs/0001-exam-bank-skill.md#invocation-and-routing), [State](../../../docs/specs/0001-exam-bank-skill.md#state), [Step 1: setup](../../../docs/specs/0001-exam-bank-skill.md#step-1-setup), [Permissions printed by setup](../../../docs/specs/0001-exam-bank-skill.md#permissions-printed-by-setup). ADR 0002.

**What to build:** The user types `/exam-bank pmle` and the skill runs the current step, then stops and prints the next command. With every source disabled and only `given` questions, that walks setup, intake and merge, one step per invocation, and then names augment, which ticket 11 builds. A forced export finishes the run. Setup checks the config and tools and prints the permission block. A script rebuilds `state.md` from the files on every invocation.

**Blocked by:** 01, 02

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** ADR 0002: nothing but the state script writes `state.md`, and only scripts write `state.json`. Setup never edits a settings file. The router stays under 60 lines and reads one step file per invocation. The builder cannot invoke the skill itself, so the user runs the live Verify steps in a fresh session.

- [x] Setup runs the five checks in order and stops at the first failure with its fix
- [x] Config validation enforces the spec's key rules for both files
- [x] A passing setup creates the exam's data folders, prints the permission block and records the pass time
- [x] The state command reruns checks 1 to 3 and routes to setup when one fails
- [x] `state.md` has the six parts in the spec's order, with notes built from the log
- [x] Step status follows the spec's table for all ten steps. Steps not built yet report from the data as it is
- [x] A forced step runs on the files as they are. An unknown step name prints the valid names and stops
- [x] A forced scrape, llm-scrape or intake reopens merge and later steps that have pending rows
- [x] The export stale rule compares an in-memory render with the files and counts the differing IDs
- [x] The router file has the spec's frontmatter and four-step procedure. Step files exist for setup, intake, merge and export
- [x] Confirm-at-build 5 and 8 are settled and recorded in the ticket comments: `$ARGUMENTS` reaches the router, only one step file loads, and the `python` command name on this platform

**Verify:**

- Run `pytest`. Setup-check tests, config validation tests and state tests over fixture data folders pass
- Set one of the three environment variables, run setup. It stops and names the variable
- Run the state command on a data folder with a `given` file and no source file. It names intake as the current step
- Run export through the entry point, edit one row's `given` block, run intake and merge, then state. The export line says pending with 1 row differing
- User, in a fresh Claude Code session: run `/exam-bank` with no exam. The four forms print
- User, with every source set to `enabled: false` in the config copy, in fresh sessions: run `/exam-bank pmle` three times. The runs do setup, intake and merge, one each, and each prints the next command. The state then names augment as the current step
- User, in a fresh session: run `/exam-bank pmle export`. The CSV appears

## Comments

- Confirm-at-build 5: isolated fresh Claude Code sessions passed `pmle` and `pmle export` through `$ARGUMENTS`; each session read exactly the one selected step file.
- Confirm-at-build 8: `python` resolves to Python 3.11.5 on this platform.
- Isolated sessions completed setup, intake, merge and forced export; the no-argument invocation printed all four forms.

## Build notes

- Added `setup` and `state` modules; `eb.py state <exam> [step]` selects the step file.
- `state` calls setup validation and the export renderer; only `state` writes `state.md`.
- Setup checks Chromium in a subprocess with a timeout; sandboxed probes may need access outside the sandbox.
