# Rundown: readme-visuals
Harness: Claude Code. Commands in its syntax, model names from its column of the tier table.
Source: .scratch/readme-visuals/issues
Workspace: C:/Users/gjand/Workstation/Foldrer/1-1 AI Assisted/GCP exam builder

## Rules

- One session per step: start a fresh session before each command, unless the step says "same session".
- Open the folder named by `Workspace:` as the project before starting each session; commands below use paths relative to it.
- Set the model and effort before you paste the command.
- Steps marked "interview" are conversations. Run one at a time.
- The tickets of one wave do not block each other. Run them one at a time, or all at once. To run a wave all at once, paste its launch block into one session; it opens a session per ticket.

## Order

```
Before you start: 01
Spec steps: done
Wave 1: 02, 05, 09, 10, 11, 12, 13, 14, 15 (parallel)
Wave 2: 03, 16
Wave 3: 04 (done)
Wave 4: 06, 07 (done)
Wave 5: 08 (done)
Retro
Ship
```

## Before you start

- [x] **01 Remove reference_pictures**. Blocked by: nothing. Blocks: 06. Model: `haiku`, effort: `low`, where: `cli`. Prerequisite: finish before the build; `git rm` only, do not commit `certsafari-live-temp.html`, no history rewrite.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/01-remove-reference-pictures.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```

## Spec steps

Spec steps: done.

## Build

Or build everything on one branch (model `opus`):

```
/starterkit:builder-spec <spec path>
```

### Wave 1: up to 7 sessions in parallel

Paste this block into one session to run the whole wave:

```
Open 7 parallel sessions, one per ticket below, each in its own worktree (user_asked, no confirmation card).
Exception: a ticket whose Constraints say "Main checkout" (09, 10) runs in this checkout (use_worktree: false), commits directly on readme-visuals, and commits only the files its ticket lists, by path.
Right after each worktree session starts, copy .claude/settings.local.json from this checkout into its worktree's .claude/ folder if it is not already there.
Start prompt for each session: implement the ticket directly, starting immediately, no questions. Never tell a session to invoke /starterkit:builder or any slash command: those are user-only and the session will stall. Use the ticket's content as the spec.
Set model and effort right after starting, using full model ids (e.g. claude-opus-5-5, claude-sonnet-5-5), not short names. If a call fails, stop and tell me; don't keep retrying.
Each session: finish every requirement in the ticket, run the ticket's Verify steps, tick every checkbox that is met, write ## Build notes on the ticket (at most five one-line notes: Modules added or removed, Interface names changed, new cross-module calls, mismatches with the docs; none when empty), mark the ticket resolved once all are ticked, commit on its branch, report anything unrun. A session can use subagents. Sessions never merge, rebase or push. Sessions never touch rundown.md; only the launching session writes it.
When all sessions report done, check each one's report and diff, then merge one at a time in ticket order: rebase the branch onto local readme-visuals (git -C the worktree), fast-forward readme-visuals to it. On conflicts, keep both sides' additions. No push.
After all merges: archive the sessions first (releases Windows folder locks), then git worktree remove --force + git worktree prune, then git branch -d each merged branch. Delete only branches fully merged into readme-visuals.
After the last merge, when the run changed a ticket: Load the `rundown` skill. Once, in this launching session.
Report: commit per ticket, unrun Verify steps, conflicts resolved, anything not cleaned up. End with the next step rundown printed.

Tickets:
- .scratch/readme-visuals/issues/09-live-google-captures.md | model: sonnet | effort: medium
- .scratch/readme-visuals/issues/10-export-summary-image.md | model: sonnet | effort: low
- .scratch/readme-visuals/issues/11-social-preview.md | model: sonnet | effort: low
- .scratch/readme-visuals/issues/12-readme-showcase.md | model: sonnet | effort: medium
- .scratch/readme-visuals/issues/13-synthetic-examtopics-fixtures.md | model: sonnet | effort: medium
- .scratch/readme-visuals/issues/14-synthetic-certsafari-fixtures.md | model: sonnet | effort: medium
- .scratch/readme-visuals/issues/15-synthetic-merge-export-fixtures.md | model: sonnet | effort: medium
```

Or one ticket at a time:

- [x] **02 Demo bank**. Blocked by: nothing. Blocks: 03, 04, 06. Model: `opus`, effort: `high`, where: `cli`. Write every question new, never read or reword `exam-bank/pmle/` or any question site, follow the 0001 CSV contract exactly.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/02-demo-bank.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [x] **05 User screenshots and masking**. Blocked by: nothing. Blocks: 06. Model: `haiku`, effort: `low`, where: `desktop`. Superseded by 09 and 10 (wontfix).
  ```
  /starterkit:builder .scratch/readme-visuals/issues/05-user-screenshots.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **09 Live Google capture and Try it check**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `medium`, where: `desktop`. Main checkout, the only GUI session; never touch existing `app/.clasp*.json`; you approve tool access, click Advanced and Allow in the OAuth popup, and say yes before the Trash step; the plugin must be installed in the desktop app, see the README Install section.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/09-live-google-captures.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **10 Export summary image**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `low`, where: `cli`. Main checkout (reads the real bank), mask on text before rendering, never print question text.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/10-export-summary-image.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **11 Social preview and About draft**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `low`, where: `cli`. Worktree, no GUI or GitHub calls, image from committed Demo bank frames and the tagline only.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/11-social-preview.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **12 README showcase and restructure**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `medium`, where: `cli`. Worktree, follow the 0001 Showcase order exactly, use the fixed asset paths, name no question site.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/12-readme-showcase.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **13 Synthetic examtopics fixtures**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `medium`, where: `cli`. Worktree, keep the page structure, invent all text, change no parser code.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/13-synthetic-examtopics-fixtures.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **14 Synthetic certsafari fixtures**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `medium`, where: `cli`. Worktree, keep the page structure, invent all text, change no parser code.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/14-synthetic-certsafari-fixtures.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **15 Synthetic merge and export fixtures**. Blocked by: nothing. Blocks: 16. Model: `sonnet`, effort: `medium`, where: `cli`. Worktree, keep fields and ID rules, regenerate the golden CSV with the export code, change no merge or export code.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/15-synthetic-merge-export-fixtures.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```

### Wave 2: one session

- [x] **03 App preview server**. Blocked by: 02. Blocks: 04. Model: `sonnet`, effort: `medium`, where: `cli`. Lives under `scripts/`, reuse the test loaders, change no app code.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/03-preview-server.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```
- [ ] **16 Publish**. Blocked by: 09, 10, 11, 12, 13, 14, 15. Blocks: nothing. Model: `opus`, effort: `high`, where: `desktop`. Main checkout; you say yes in chat before each push, rename, repo create, `gh repo edit` and preview upload; public commit uses your GitHub noreply email; no force-push or history rewrite; the plugin must be installed in the desktop app, see the README Install section.
  ```
  /starterkit:builder .scratch/readme-visuals/issues/16-publish.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```

### Wave 3

Wave 3: done (04).

### Wave 4

Wave 4: done (06, 07).

### Wave 5

Wave 5: done (08).

## Retro

- [ ] **Retro**. Model: `opus`. Run before clearing the last build session.
  ```
  /starterkit:retro
  ```

## Ship

- [ ] **Ship**. Model: `sonnet`, effort: `low`. (fresh session)
  ```
  /starterkit:ship .scratch/readme-visuals
  ```
