# Rundown: exam-bank-skill
Harness: Codex. Commands in its syntax, model names from its column of the tier table.
Source: .scratch/exam-bank-skill/issues
Workspace: C:/Users/gjand/Workstation/Foldrer/1-1 AI Assisted/GCP exam builder

## Rules

- Open the Workspace folder as the project before starting each session; commands use paths relative to it.

- One session per step: start a fresh session before each command, unless the step says "same session".
- Set the model and effort before you paste the command.
- Steps marked "interview" are conversations. Run one at a time.
- The tickets of one wave do not block each other. Run them one at a time, or all at once. To run a wave all at once, give each ticket its own session.

## Order

```
Before you start: 01
Spec steps: done
Wave 1: 02 (done)
Wave 2: 03, 07 (done)
Wave 3: 04, 08 (done)
Wave 4: 05, 09, 10 (done)
Wave 5: 06, 11, 12 (done)
Wave 6: 13 (done)
Wave 7: 14 (done)
Retro
Ship
```

## Before you start

- [x] **01 Repo scaffold and pytest**. Blocked by: nothing. Blocks: 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14. Model: `gpt-6-luna`, effort: `low`, where: `cli`. Prerequisite: finish before the build. No version pins in the runtime requirements. Ship no settings file with permissions. Write no root README here (ticket 14). Make no commit unless the user asks.
  ```
  $builder .scratch/exam-bank-skill/issues/01-repo-scaffold-and-pytest.md Finish every requirement in the ticket, then tick every checkbox in the ticket. You can use subagents to finish the ticket.
  ```

## Spec steps

Spec steps: done.

## Build

Or build everything on one branch (model `gpt-6-astra`):

```
$builder-spec <spec path>
```

### Wave 1: done (02).

### Wave 2: done (03, 07).

### Wave 3: done (04, 08).

### Wave 4: done (05, 09, 10).

### Wave 5: done (06, 11, 12).

### Wave 6: done (13).

### Wave 7: done (14).

## Retro

- [x] **Retro**. Model: `gpt-6-astra`. Run before clearing the last build session.
  ```
  $retro
  ```

## Ship

- [x] **Ship**. Model: `gpt-6.1-sol`, effort: `low`. (fresh session)
  ```
  $ship .scratch/exam-bank-skill
  ```
