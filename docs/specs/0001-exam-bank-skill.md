# 0001: exam-bank skill

Status: building
Reviewed: 2026-11-17

Build-ready spec for the `exam-bank` Claude Code skill. The skill builds one deduplicated, fully answered **Question bank** per exam and exports it as a CSV for the study app ([0002](0002-study-app.md)).

Sources: decisions D1 to D361 and D379 to D387 in `.scratch/gcp-exam-sim/interview-log.md`, ADRs 0001 to 0004 in `docs/adr/`, vocabulary in `GLOSSARY.md`.

## How to read this spec

- Each section opens with a `Decisions:` line naming the D-numbers and ADRs it rests on.
- A mark like `[G3]` means no D-number covered the point, or two disagreed. The user settled every one on 2026-11-17, and the text beside the mark is the decision. [Decision gaps](#decision-gaps) maps each mark to its D-number.
- Items a live check must settle before the README is written are in [Confirm at build](#confirm-at-build).
- Each rule appears once. Other sections link to it.

## Scope

Decisions: D2, D3, D16, D18, D21, D22, D24, D35, D144.

In scope: skill files, config, scripts, workers, the data folder, the exported CSV and `bank_meta.json`, the skill-owned README parts.

Out of scope: the app (0002), near-duplicate detection, questions that need an image exhibit, publishing the bank, **Study guide** chapters inside the app.

One **Question bank** per exam. First exam is PMLE, slug `pmle`. Another exam is a new `exams/<slug>.yaml` and a new data folder, with no code change.

## Repo layout and install

Decisions: D21, D51, D61, D65, D87, D252, D322, D326, D327, D335.

```
.claude/
  skills/exam-bank/
    SKILL.md                 router, stays in context, under 60 lines
    dispatch.md              shared fan-out procedure
    steps/
      01-setup.md  02-scrape.md  03-llm-scrape.md  04-intake.md  05-merge.md
      06-tag.md  07-answers.md  08-explanations.md  09-augment.md  10-export.md
      study-guide.md  recheck.md
    workers/
      llm-scrape.md  tag.md  answers.md  explanations.md  augment.md  study-guide.md
    scripts/
      eb.py                  single entry point, see Scripts
      scrapers/examtopics.py  scrapers/certsafari.py
      tests/                 pytest, see Tests
    templates/
      models.example.yaml
      exams/pmle.example.yaml
      given-example.md
      import-steps.txt
  agents/
    exam-bank-reader.md      tools: Read, Write            [G9]
    exam-bank-researcher.md  tools: Read, Write, WebSearch, WebFetch   [G9]
app/                         study app source (0002)
docs/specs/  docs/adr/
requirements.txt             requests, beautifulsoup4, playwright, pyyaml
requirements-dev.txt         pytest
.gitignore                   exam-bank/ and .claude/settings.local.json (0002 adds its own lines)
LICENSE                      MIT
README.md                    assembled last, see README parts
exam-bank/                   gitignored, never committed
  config/
    models.yaml
    exams/<slug>.yaml
  .browser/<site>/           Playwright persistent profile per Curated site
  <slug>/
    given/*.md               user-written questions
    raw/<source>/<page>.html, <page>.txt, <page>.meta.json
    sources/<name>.jsonl     one per source
    sources/<site>.progress.json   per Curated site, see Step 2
    bank.jsonl
    bank_meta.json
    batches/<step>/manifest.json, <batch_id>.in.json, <batch_id>.json
    reports/*.csv            downloaded Reports tab
    export/<slug>-questions.csv
    study-guide/<subdomain>-<title-slug>.md
    state.md  state.json  study_guide_state.md  log.jsonl
```

Install is a clone plus two commands: `pip install -r requirements.txt`, then `playwright install chromium`. Nothing is copied into `.claude/`. `git pull` updates the skill. No `.claude/settings.json` ships with permissions.

`requirements.txt` lists the four packages without version pins.

## Config

Decisions: D19, D49 to D54, D58, D77, D94, D114, D120, D130, D134, D148, D229, D235, D238, D250, D327, D379.

Both files are YAML under `exam-bank/config/`. `setup` validates them. Scripts read them. The main session reads only the values a script prints.

### models.yaml

Shipped as `templates/models.example.yaml` with exactly this content:

```yaml
# alias: opus | sonnet | haiku | fable.  effort: low | medium | high | xhigh | max
defaults:
  batch_size: 5
  max_parallel: 10          # values above 20 are clamped to 20

tasks:
  llm_scraping:        {alias: sonnet, effort: medium}   # one page per Batch, batch_size unused
  subdomain_tagging:   {alias: sonnet, effort: low, batch_size: 20}
  answer_filling:      {alias: opus,   effort: high}
  explanation_writing: {alias: opus,   effort: medium}
  augmentation:        {alias: opus,   effort: high}
  report_recheck:      {alias: opus,   effort: high}
  study_guide_chapter: {alias: sonnet, effort: medium}

augment:
  target_total: 400
  min_per_subdomain: 15
  max_created_per_run: 100

study_guide:
  max_questions: 80
```

A task may set its own `batch_size` and `max_parallel`. The seven tasks above are the full list `[G5]`.

| Task | Used by |
|---|---|
| `llm_scraping` | `llm-scrape` |
| `subdomain_tagging` | `tag` |
| `answer_filling` | `answers`, and the `verify` **Batches** of `augment` |
| `explanation_writing` | `explanations` |
| `augmentation` | create **Batches** of `augment` |
| `report_recheck` | `recheck` |
| `study_guide_chapter` | `study-guide` |

### The exam file

Shipped as `templates/exams/pmle.example.yaml` with exactly this content:

```yaml
slug: pmle
name: Google Cloud Professional Machine Learning Engineer
guide_version: "2026-06-01"

sections:
  - number: 1
    title: Architecting low-code AI solutions
    weight: 13
    subdomains:
      - {number: "1.1", title: "Developing ML models using BigQuery ML or AutoML on Gemini Enterprise Agent Platform"}
      - {number: "1.2", title: "Building AI solutions using Google Cloud AI APIs or foundational models"}
  - number: 2
    title: Collaborating within and across teams to manage data and models
    weight: 16
    subdomains:
      - {number: "2.1", title: "Exploring and preprocessing data for ML"}
      - {number: "2.2", title: "Model prototyping using notebooks (e.g., Agent Platform Workbench and Colab Enterprise)"}
      - {number: "2.3", title: "Tracking and running ML experiments"}
  - number: 3
    title: Scaling prototypes into ML models
    weight: 21
    subdomains:
      - {number: "3.1", title: "Building models given the task considering cost, complexity, latency, and scalability"}
      - {number: "3.2", title: "Training models"}
      - {number: "3.3", title: "Choosing appropriate hardware for training"}
  - number: 4
    title: Serving and scaling models
    weight: 20
    subdomains:
      - {number: "4.1", title: "Serving models"}
      - {number: "4.2", title: "Scaling online model serving"}
  - number: 5
    title: Automating and orchestrating ML pipelines
    weight: 18
    subdomains:
      - {number: "5.1", title: "Developing end-to-end ML pipelines"}
      - {number: "5.2", title: "Automating model retraining"}
  - number: 6
    title: Monitoring AI solutions
    weight: 13
    subdomains:
      - {number: "6.1", title: "Identifying risks to AI solutions"}
      - {number: "6.2", title: "Monitoring, testing, and troubleshooting AI solutions"}

curated_sites:                 # each name has a scraper in scripts/scrapers/<name>.py
  - name: examtopics
    url: https://www.examtopics.com/exams/google/professional-machine-learning-engineer/view/
    enabled: true
    answers_trusted: true
  - name: certsafari
    url: https://www.certsafari.com/google/machine-learning-engineer-professional/practice-questions
    enabled: true
    answers_trusted: true

llm_sources:                   # static pages only, read the site's ToS before enabling
  - name: whizlabs
    urls: ["https://www.whizlabs.com/blog/gcp-professional-machine-learning-engineer-questions/"]
    enabled: true
    answers_trusted: false
  - name: theserverside
    urls: ["https://www.theserverside.com/blog/Coffee-Talk-Java-News-Stories-and-Opinions/GCP-Professional-ML-Engineer-Certification-Exam-Dump-and-Braindump/"]
    enabled: true
    answers_trusted: false
  - name: mockingowl
    urls: ["https://mockingowl.pages.dev/exams/google/gcp-pmle/sample-questions/"]
    enabled: true
    answers_trusted: false
  - name: open-exam-prep
    urls: ["https://open-exam-prep.com/practice/gcp-machine-learning"]
    enabled: true
    answers_trusted: false
```

Key rules:

- `slug` equals the file name and the `<exam>` argument.
- **Subdomain** numbers are strings, unique, and start with their **Section** number. A **Subdomain** may carry an optional `hint` string naming products and tasks, used only by the `tag` worker (D229).
- `weight` is the published **Section** weight. Weights need no fixed sum (PMLE sums to 101).
- Source names are unique across `curated_sites` and `llm_sources`, lowercase, `[a-z0-9-]`. The names `given` and `created` are reserved.
- `answers_trusted` defaults to `true` for a **Curated site** and `false` for an LLM-scrape source (D94).
- v1 ships two **Curated site** scrapers `[G1]`: `examtopics` (all pages, user logs in) and `certsafari` (the 35-question sample page only, since robots.txt disallows the quiz path and D4 drops what a site forbids). ITExams gets no scraper.

## Invocation and routing

Decisions: D21, D59, D60, D65, D69, D71, D73, D75, D129, D217. Research: `.scratch/gcp-exam-sim/research/claude-skill-mechanics.md`.

`SKILL.md` frontmatter:

```yaml
---
name: exam-bank
description: Build and export a Question bank for one exam, one step per run.
disable-model-invocation: true
argument-hint: <exam> [step] [args]
---
```

Forms:

| Command | Runs |
|---|---|
| `/exam-bank <exam>` | the current step from state |
| `/exam-bank <exam> <step>` | that step, forced. Names: `setup`, `scrape`, `llm-scrape`, `intake`, `merge`, `tag`, `answers`, `explanations`, `augment`, `export` |
| `/exam-bank <exam> study-guide [<subdomain>] [redo]` | the **Study guide** route |
| `/exam-bank <exam> recheck` | the **Report** re-check route |

Router procedure, the whole body of `SKILL.md`:

1. Read the arguments from `$ARGUMENTS`. No exam: print the four forms and stop.
2. Run `python .claude/skills/exam-bank/scripts/eb.py state <exam> [step]`. It rebuilds `state.md` and prints the step to run and its step file. An unknown step name prints the valid names and stops.
3. Read that one step file with the Read tool and follow it. Read no other step file.
4. Run `eb.py state <exam>` again. Print its summary and the next command. Stop.

One invocation runs one step, then stops. The user starts a fresh session for the next command. The main session only runs scripts, dispatches subagents and reports. Every LLM task runs in a subagent with the alias and effort from `models.yaml`.

Forced steps:

- A forced `scrape`, `llm-scrape` or `intake` followed by `/exam-bank <exam>` reopens `merge` and every later step that has pending rows. No manual reset exists.
- A forced step runs on the files as they are, also when an earlier step is pending `[G18]`. `export` still refuses incomplete rows.
- A forced `augment` plans new gaps (D119).

## State

Decisions: D61 to D64, D66, D67, D69, D75, D76, D84, D90, D231, D251, D266, D319. ADR 0002.

`eb.py state` rebuilds `state.md` on every invocation from the files. Nothing else writes it. Only scripts write `state.json`.

### state.md

In this order:

1. Header: exam slug and name, current step, next command.
2. Step checklist, ten lines, each `pending`, `in progress`, `waiting on user`, `done` or `skipped`.
3. Source table: name, kind, status, pages done / total, question count, last run. Status can be `waiting on user: <action>` or `failed: <reason>`, and a failed page of a multi-page source gets its own line.
4. Per-step **Batch** counts: total, done, pending, failed, with failed **Batch** ids.
5. Notes built from `log.jsonl`: skipped questions by source and reason, bad given blocks by `file:line`, given keys no longer in `given/`, dropped `llm-scrape` questions by source and number, dropped `created` records, retired rows with reason, count of `low` **Subdomain** tags, augment drops.
6. Export line: `done`, or `pending: bank changed since last export (N rows differ)`.

### Step status

The current step is the first step in order that is not `done` or `skipped`.

| Step | Pending when | Skipped when |
|---|---|---|
| `setup` | `state.json` has no `setup.passed_at`, or a check fails now `[G7]` | never |
| `scrape` | an enabled **Curated site** has pages left. `waiting on user` when its gate is set | no enabled **Curated site** |
| `llm-scrape` | a page of an enabled source has neither a valid result nor a `failed` record | no enabled `llm_sources` entry |
| `intake` | `given/*.md` exists and `sources/given.jsonl` does not | no file in `given/` |
| `merge` | a `sources/*.jsonl` hash differs from `state.json` `merged`, or the exam YAML `guide_version` differs from `bank_meta.json` | never |
| `tag` | an `active` row has an empty `subdomain` | never |
| `answers` | an `active` row has an empty answer or `uncertain` TRUE, and no `answer_checked_at` | never |
| `explanations` | an `active` row is not pending for `answers` and a choice lacks an explanation | never |
| `augment` | `augment.opt_in` is unset, or it is true and a manifest **Batch** has no valid result | `augment.opt_in` is false |
| `export` | the render differs from the files, see [Step 10](#step-10-export) | never |

A step with some **Batches** applied and some pending shows `in progress`. A step is `done` when the script finds no pending work. An edit under `given/` needs a forced `intake`, since `intake` does not watch the files (D69, D84).

### state.json

```json
{
  "setup": {"passed_at": "2026-11-17T08:00:00Z"},
  "augment": {"opt_in": true, "asked_at": "2026-11-17T09:00:00Z"},
  "gates": {"examtopics": "Log in to ExamTopics in the open browser window, then rerun /exam-bank pmle scrape"},
  "merged": {"sources/examtopics.jsonl": "<sha256>", "sources/given.jsonl": "<sha256>"}
}
```

### log.jsonl

Append-only, one object per event: `{at, step, kind, source, ref, reason}`. `kind` is one of `skipped`, `bad_block`, `missing_key`, `dropped`, `retired`, `warning`, `failed_page`. `state.md` notes come from here.

## Dispatch

Decisions: D53, D63, D67, D68, D71, D72, D74, D107, D218, D240, D251, D381, D386, D387. ADR 0002.

`dispatch.md` holds this procedure. Steps `llm-scrape`, `tag`, `answers`, `explanations`, `augment` and the `recheck` route follow it. `study-guide` does not.

1. Run `eb.py batches <exam> <step>`. The script forms **Batches** from all pending work, appends them to `batches/<step>/manifest.json`, writes one `<batch_id>.in.json` each, and prints a dispatch list: batch id, input path, result path, worker file, agent type, alias, effort. It also prints `max_parallel`.
2. Spawn the first `max_parallel` **Batches** as Agent calls in one message. Each call passes `subagent_type`, `model` (the alias) and `effort` from the list, and this prompt with the paths filled in:
   `Read <worker file> and follow it. Input: <input path>. Write your result to <result path>. Reply with one line: <batch_id> done.`
3. When the wave returns, run `eb.py apply <exam> <step>`. It validates every new result file, applies the valid questions, requeues the rest, and prints the next dispatch list.
4. Repeat 2 and 3 until `apply` prints an empty list. Report its counts.

Rules:

- No subagent reads or writes `bank.jsonl`. A worker reads its input file and its worker file, and writes one result file.
- A **Batch** id is `<step>-<4-digit sequence>`, for example `answers-0007`. In `tag`, `answers`, `explanations` and `recheck`, a **Batch** holds pending question IDs in bank order, `batch_size` each.
- The manifest is a JSON array. An entry is never edited: `{batch_id, kind, items, attempt, retry_of, created_at}`. `kind` is the step name, or `create` / `verify` in `augment`. `items` are question IDs, a page reference, or a **Subdomain** with a count.
- A **Batch** is pending when its entry has no valid result file and no later entry names it in `retry_of`. A result file is valid when it parses and its `batch_id` and `step` match the entry.
- Retry: a **Batch** with no valid file is requeued as a new entry with `attempt` + 1 and `retry_of` set `[G17]`.
- Partial result: the valid questions apply. The rejected ones go into a new **Batch** with `attempt` + 1 and `retry_of` set.
- After attempt 3 nothing is requeued. The entry is `failed`, its open questions stay pending, and `state.md` lists it. A later invocation starts them again at attempt 1. `llm-scrape` differs: it drops the open questions and counts the page done, see [Step 3](#step-3-llm-scrape).
- Auto-retire (D381, D387): in `tag`, `answers` and `explanations`, the script retires a question that validation rejected in two `failed` entries: `status: retired`, the reason in `log.jsonl`, a line in `state.md`. Only an entry whose result file parsed and rejected that question counts. An entry with no result file (usage limit, outage, permission prompt) never counts, so a bad run retires nothing. Two such entries mean two separate invocations. This keeps one question from blocking `export`. `recheck` is exempt (D386): the row stays `active`, its **Report** stays open, and `state.md` lists it.
- Results apply by question ID, so applying a file twice changes nothing.

Done when `eb.py apply` prints an empty list and every manifest entry is applied, superseded or `failed`.

## Bank data

Decisions: D15, D16, D20, D26 to D48, D91, D96, D99, D112, D125, D219, D227, D228, D231, D252, D379. ADR 0001.

### bank.jsonl

One JSON object per line, one line per question, in first-merge order. Rows are never deleted.

| Field | Type | In CSV | Notes |
|---|---|---|---|
| `id` | string | yes | see [CSV contract](#csv-contract) |
| `exam` | string | yes | slug |
| `status` | `active` / `retired` | yes | |
| `subdomain` | string | yes | number only, empty until tagged |
| `subdomain_by` | `source` / `user` / `llm` | no | |
| `subdomain_confidence` | `high` / `medium` / `low` | no | set by `tag` only |
| `question` | string | yes | plain text, see cell text rule |
| `choices` | list of `{letter, text, explanation, explanation_by}` | yes | 2 to 6, stored order |
| `answer` | list of letters | yes | sorted, may be empty until `answers` |
| `answer_by` | `source` / `user` / `llm` | yes | |
| `answer_confidence` | `high` / `medium` / `low` | no | |
| `answer_note` | string | no | one line |
| `answer_refs` | list of URLs | no | pages the session fetched |
| `answer_checked_at` | timestamp | no | empty means unchecked |
| `explanation_by` | `source` / `user` / `llm` | yes | `llm` when any choice is LLM-written, `user` when the user wrote every one, else `source` |
| `lineage` | `scraped` / `given` / `created` | yes | |
| `sources` | list of source records | flattened | below |
| `uncertain` | boolean | yes | |
| `derived_from` | list of IDs | yes | `created` rows only |
| `updated_at` | timestamp | yes | moves when question text, choices, answer or explanations change. A tag, a retire, or a confirming re-check that rewrites no explanation leaves it (D40, D224, D231) |
| `rechecked_at` | timestamp | yes | empty until a re-check |
| `recheck_note` | string | yes | empty until a re-check |

Source record: `{name, url, source_question_no, site_answer, community_answer, scraped_at, subdomain_label, explanation_block, unsure}`.

- `site_answer` and `community_answer` are letter lists in the stored choice order of the row. `community_answer` is filled by ExamTopics only.
- `subdomain_label` is the raw label text the source printed, else empty.
- `explanation_block` holds a source's single undivided explanation. It is input for the LLM and never exported `[G14]`.
- `unsure` is true only on a `given` record with `Unsure: yes`.

Timestamps are ISO 8601 UTC, `YYYY-MM-DDTHH:MM:SSZ`.

### Per-source files

`sources/<name>.jsonl` uses the row shape without `id`, with exactly one record in `sources`, and only the fields the source gives. `merge` assigns the ID.

| File | Written by | Lineage |
|---|---|---|
| `sources/<curated site>.jsonl` | `scrape` | `scraped` |
| `sources/<llm source>.jsonl` | `llm-scrape` apply | `scraped` |
| `sources/given.jsonl` | `intake`, rewritten in full each run | `given` |
| `sources/created.jsonl` | `augment` apply | `created` |

### bank_meta.json

One file beside `bank.jsonl` `[G2]`:

```json
{
  "schema_version": 1,
  "exam": "pmle",
  "guide_version": "2026-06-01",
  "exported_at": "2026-11-17T10:00:00Z",
  "section_weights": "1:13,2:16,3:21,4:20,5:18,6:13"
}
```

`merge` writes `schema_version`, `exam` and `guide_version`. `export` rewrites the whole file. The app never reads it.

### Cell text rule

Question, choice and explanation text is plain text with line breaks, and backticks around code. No HTML and no other Markdown (D42). Scripts reject LLM output that has, outside backtick spans, an HTML tag, a Markdown link `](`, a line starting with `#`, or `**`.

## Step 1: setup

Decisions: D70, D97, D242, D326, D328.

A script step with no subagent. `eb.py setup <exam>` checks, in order, and stops at the first failure with the fix:

1. `exam-bank/config/models.yaml` and `exam-bank/config/exams/<exam>.yaml` exist. Fix text gives the two copy commands from [README parts](#readme-parts).
2. Both files pass the key rules in [Config](#config).
3. `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` and `CLAUDE_CODE_EFFORT_LEVEL` are unset. Any of them overrides the per-task alias and effort without a word.
4. Python is 3.11 or newer, and `requests`, `bs4`, `playwright` and `yaml` import.
5. Playwright's Chromium is installed.

On a pass it creates the folders under `exam-bank/<exam>/`, prints the permission block from [Permissions printed by setup](#permissions-printed-by-setup), and writes `setup.passed_at`. It never edits a settings file.

`eb.py state` reruns checks 1 to 3 on every invocation and routes to `setup` when one fails `[G7]`.

Done when all five checks pass and `state.json` holds `setup.passed_at`.

## Step 2: scrape

Decisions: D4, D22, D29, D64, D93. Tickets 01, 02, 03.

A script step with no subagent. `eb.py scrape <exam>` runs the scraper of every enabled **Curated site** that has pages left. The step file starts it as a background command and waits for it to exit.

Shared scraper rules:

- Playwright, headed Chromium, persistent profile in `exam-bank/.browser/<site>/`. One page at a time, a random 3 to 8 second pause between pages `[G15]`.
- The script obeys `robots.txt`. It types no credentials and solves no CAPTCHA. The user does both in the visible window.
- Wait for the user: when a page shows a login gate or a challenge in place of question cards, the script writes the site's gate with the exact action into `state.json`, keeps the window open and polls every 5 seconds for up to 8 minutes `[G15]`. Cards appear: it clears the gate and goes on. Time runs out: it closes and exits. A rerun continues from the last saved page.
- After each page it saves the raw HTML to `raw/<site>/page-<N>.html`, appends that page's records to `sources/<site>.jsonl`, and updates `sources/<site>.progress.json` (`pages_done`, `pages_total`, `last_run`).
- A question with an image, or with under 2 or over 6 choices, is skipped and logged.
- Text is stored verbatim after the [cell text rule](#cell-text-rule): HTML to plain text, code in backticks, UTF-8.

`examtopics`:

- Pages: the config URL is page 1, then `<url>N/` for N from 2 to the page count read from "Viewing page 1 out of N pages". Ten questions per page. Page 2 onward needs the user's login.
- Per question: number, stem, choices, site answer from the "Correct Answer" line, community answer from the option tagged "Most Voted" (empty when no tag). No explanations. No discussion requests. No vote shares (D93).
- Record: `source_question_no` = the question number, `url` = the page URL.

`certsafari`:

- One page, the config URL. `requests` plus `beautifulsoup4` when answers sit in the static HTML, else Playwright with a click on each "Show answer & explanation".
- Per question: position number, stem, choices A to E, the "Correct answer" letters, one explanation per choice, and the `Subdomain X.Y: <title>` line above its group as `subdomain_label`.
- Record: `source_question_no` = position on the page, `url` = the page URL.

Selectors for both sites are unverified, see [Confirm at build](#confirm-at-build).

Done when every enabled site shows pages done equal to pages total, or the step ended with a gate set and the action printed.

## Step 3: llm-scrape

Decisions: D237 to D253, D266, D267. ADR 0004. Ticket 19.

Runs on the shared [dispatch](#dispatch). One **Batch** is one page URL.

Fetch, by script before any **Batch** forms:

1. For each URL of each enabled `llm_sources` entry, read `robots.txt`. A disallowed URL is `failed: robots`.
2. Download with `requests` and the User-Agent `Mozilla/5.0 (compatible; exam-bank)`. No user detail goes into any request. A non-200 answer is `failed: http <code>`.
3. Save `raw/<source>/<NN>.html` and the `beautifulsoup4` text as `<NN>.txt`, where `NN` is the URL's two-digit position in the entry. Save `<NN>.meta.json` with `url`, `fetched_at`, `sha256_txt`, `status`.
4. A `.txt` over 150,000 characters is `failed: too large`.
5. A page whose text hash is unchanged and that already has a valid result is skipped. A page that failed before is fetched again.

Every page gets `<NN>.meta.json`, also on failure, with `status` `ok` or `failed: <reason>`. This is the page's `failed` record. `apply` writes `failed: no questions` there, and `done-partial` when attempt 3 drops questions.

Failure is per page. The step skips a failed page, lists it in `state.md` with its reason, and still finishes. There is no browser and no `waiting on user` here. The user can put those questions in `given/`.

Worker `workers/llm-scrape.md`, agent type `exam-bank-reader`, task `llm_scraping`:

- Input `batches/llm-scrape/<batch_id>.in.json`: `{batch_id, step, source, url, txt_path}`.
- Copy question, choices and explanation text verbatim from the `.txt`. Leave typos as they are.
- Record an answer only when the page ties it clearly to that question. Otherwise leave it empty. Step 7 works answers out.
- Explanations go per choice when the page splits them so, else as one block.
- Return `skipped` with a reason for a question with an image, or with under 2 or over 6 choices.

Result `batches/llm-scrape/<batch_id>.json`:

```json
{"batch_id": "llm-scrape-0002", "step": "llm-scrape", "results": [
  {"n": 7, "status": "ok", "question": "...", "choices": ["...", "..."],
   "answer": ["B"], "explanations": {"A": "...", "B": "..."}, "subdomain_label": ""},
  {"n": 8, "status": "ok", "question": "...", "choices": ["...", "..."],
   "answer": [], "explanations": {"block": "..."}, "subdomain_label": ""},
  {"n": 9, "status": "skipped", "reason": "Needs an image."}
]}
```

`n` is the source question number. Letters follow the order of `choices`.

Validation, per question: the stem, every choice and every explanation must be found in the `.txt` after [normalization](#id-rules); answer letters must lie within the choices. A page with zero `ok` questions is `failed: no questions`.

Rejected questions requeue. After the third attempt the script keeps the valid questions, drops the rest, lists them in `state.md` by source and question number, and counts the page done (D251).

Apply: the script writes `sources/<name>.jsonl`. A changed page replaces its own records. Source record: `name`, page `url`, `source_question_no` = `n`, `site_answer`, `scraped_at` = fetch time, `subdomain_label`, `explanation_block`. A question that left the page stays in the bank.

Done when every enabled page has a valid result or a `failed` record.

## Step 4: intake

Decisions: D77 to D92, D382. Ticket 12.

A script step with no LLM. `eb.py intake <exam>` parses every `given/*.md` and rewrites `sources/given.jsonl`.

`templates/given-example.md` ships with exactly this content. The README links it, and it is never copied into `given/`:

~~~markdown
## g-001
Subdomain: 2.1

Which two steps reduce training-serving skew?

- [x] Use the same transform code in training and serving.
  Why: One code path, so features match at both ends.
- [ ] Retrain the model every day.
  Why: Fresh weights do not fix a feature mismatch.
- [x] Export the transforms as a TFX Transform graph.
- [ ] Increase the serving batch size.

## g-002
Unsure: yes

Which command prints the active project?

```bash
gcloud config list
```

- [x] `gcloud config get-value project`
- [ ] `gcloud projects describe`
- [ ] `gcloud auth list`

## g-003

A question with no ticks. Step 7 fills the answer.

- [ ] Choice one
- [ ] Choice two
~~~

Format:

- A question starts at a `## <key>` heading. The key is unique across `given/`. Text before a file's first heading is ignored.
- Optional lines right under the heading: `Subdomain: <number>` and `Unsure: yes`.
- Question text runs from there to the first choice line.
- A choice is `- [ ] text` or `- [x] text`. Ticks mark correct choices. Letters come from choice order. No tick means no answer.
- An indented `Why:` line under a choice is its explanation, and runs to the next choice or heading.
- Inside a code fence every line is text, so code may hold `- [x]` or `## `.

Bad blocks are skipped and logged by `file:line`: under 2 or over 6 choices, no question text, duplicate key, an image `![`. Valid blocks go on and the step is `done`. A `Subdomain` number missing from the exam config is dropped with a warning.

Record: `lineage: given`, `answer` = ticked letters, `subdomain` when valid, per-choice `explanation_by: user` for each `Why:`. Source record: `name: given`, `url: given/<file>.md#<key>`, `source_question_no` = key, `site_answer` = ticked letters, `scraped_at` = intake time, `unsure`.

Google's official sample questions enter here too (D382). The sample is a Google Form that no scraper or `llm-scrape` fetch can read, so the user types the questions into a `given/` file, ticks only the answers the form reveals, and sets `Unsure: yes` on the rest.

Done when `sources/given.jsonl` reflects every valid block and every bad block is in `log.jsonl`.

## Step 5: merge

Decisions: D16, D26, D27, D30, D31, D47, D48, D85, D88 to D90, D93 to D96, D127, D227, D228, D233, D234. ADR 0001. Tickets 09, 12, 13, 20.

A script step with no LLM. Same input gives the same output. `eb.py merge <exam>` reads source files in this order: `given`, **Curated sites** in config order, LLM-scrape sources in config order, `created`.

Per incoming record:

1. A `given` record whose key matches a row's `given` source record updates that row in place: text, choices, ticks, explanations. The ID stays. Letters in `answer` and in every source record are remapped when choices moved.
2. A record already attached to a row, found by `name`, `url` and `source_question_no`, and only when the incoming hash equals that row's `id` or its current-text hash, refreshes that source record and goes no further. This keeps a full rerun from treating a `created` row as its own duplicate. A key match with a different hash logs a `warning` and goes on to 3, since `source_question_no` is a page position for CertSafari and LLM-scrape sources.
3. Otherwise compute the hash and run the dedupe compare of the [ID rules](#id-rules).
4. On a match: a `created` record is dropped and logged, and the row stays as it is. Any other record is attached as a new source record. Its letters are remapped into the stored choice order before anything is stored or compared. A `given` record sets `lineage: given`.
5. No match: a new row. `id` = the hash, `status: active`, choices in this source's order, `lineage` by source kind. A `created` record brings its whole row along: answer, explanations, `subdomain`, `answer_checked_at`, `derived_from`.

Then, on every row touched in this run:

- **Subdomain** label: keep a source label only when its number and its normalized title both equal one config entry. Then `subdomain_by: source`. A valid `given` `Subdomain:` line sets `subdomain_by: user` and wins. Number only, an old title, or two sources that disagree leave `subdomain` empty, and the labels go to `tag` as a hint.
- Stored answer `[G4]`: ticks from a `given` record without `unsure` win on any row: `answer` = the ticks, `answer_by: user`. When that changes the stored answer, the LLM-written explanations are cleared so step 8 writes them for the ticks (D100, D360). On rows whose `answer_by` is not `llm`, otherwise: ticks with `unsure`, else the first trusted source's `site_answer`, else the first untrusted source's. `answer_by` is `user` or `source`.
- Stored explanations, where no LLM text exists `[G14]`: the user's `Why:` lines, else the first source that gives one explanation for every choice.
- `uncertain` becomes TRUE when a rule below fires. `merge` never sets it FALSE on an existing row `[G3]`. New rows start FALSE.
- `answer_checked_at` is cleared when a new or changed source answer differs from the stored answer.
- `updated_at` is set when question text, choices, answer or explanations changed.

**Uncertain answer** rules:

1. Two source answers on the row differ, user ticks included (D31, D85).
2. A source record's `site_answer` differs from its own `community_answer` (D93).
3. The answer comes from a source with `answers_trusted: false`, and no trusted source gives the same letters (D94) `[G4]`. `given` and `created` count as trusted (D125).
4. A `given` record has `unsure` true (D86).

Edits to a `given` block:

- A change to question text or choices clears the LLM-written answer and every LLM-written explanation, and clears `answer_checked_at`. User-written content stays. The **Subdomain** tag stays (D234).
- A removed block leaves its row unchanged. The missing key is logged.

Guide version: when the exam YAML `guide_version` differs from `bank_meta.json`, clear every tag whose `subdomain_by` is not `user`, rerun the label match, clear with a warning any user tag missing from the new config, then write the new `guide_version` to `bank_meta.json` `[G2]`.

Last, `merge` records each source file's hash in `state.json` `merged`.

Done when every source record is attached to exactly one row or logged as dropped, and `merged` matches the files.

## Step 6: tag

Decisions: D58, D227 to D235. Ticket 20.

Runs on the shared dispatch. Pending row: see [Step status](#step-status). Worker `workers/tag.md`, agent type `exam-bank-reader`, task `subdomain_tagging`.

Input `batches/tag/<batch_id>.in.json`: the full **Section** and **Subdomain** title list with any `hint`, then per question `id`, `question`, `choices` and the source label hints. No answers.

Worker rules:

- Pick the **Subdomain** of the decision the stem's final ask calls for, over the scenario background. Still tied: the one whose title or hint names the product in the correct-looking choices. Return the runner-up as `alt`.
- Always pick the nearest **Subdomain**. Use `low` confidence when unsure.
- `unusable` only for a broken question: garbled text or missing choices.

Result `batches/tag/<batch_id>.json`:

```json
{"batch_id": "tag-0003", "step": "tag", "results": [
  {"id": "q_3fa9c21b07de", "status": "ok", "subdomain": "5.1", "confidence": "medium", "alt": "5.2"},
  {"id": "q_0b1c2d3e4f5a", "status": "unusable", "reason": "Stem cut off."}
]}
```

Validation, per question: ID in the **Batch**; `subdomain` and `alt` in the exam config; `alt` differs from `subdomain`; confidence in the enum; `unusable` has a reason. `alt` is optional.

Apply: `ok` sets `subdomain`, `subdomain_by: llm`, `subdomain_confidence`. `updated_at` stays. `alt` stays in the result file. `unusable` sets `status: retired` and logs the reason.

Done when no `active` row has an empty `subdomain`.

## Step 7: answers

Decisions: D5, D57, D93 to D113, D383, D385. Ticket 13.

Runs on the shared dispatch. Pending row: see [Step status](#step-status). Worker `workers/answers.md`, agent type `exam-bank-researcher`, task `answer_filling`.

Input `batches/answers/<batch_id>.in.json`:

```json
{"batch_id": "answers-0007", "step": "answers",
 "questions": [
   {"id": "q_3fa9c21b07de", "question": "...",
    "choices": [{"letter": "A", "text": "..."}, {"letter": "B", "text": "..."}]}
 ],
 "source_answers": {
   "q_3fa9c21b07de": {"stored": ["B"], "sources": [
     {"name": "examtopics", "answer": ["B"]}, {"name": "examtopics-community", "answer": ["A", "C"]}],
     "explanations": {"A": {"text": "...", "by": "source"}},
     "explanation_blocks": ["..."]}
 }}
```

Existing explanations sit in the `source_answers` section, apart from the choices, since they open with "Correct." or "Incorrect." and would give the answer away before the blind pass `[G21]`.

Worker rules:

1. Answer each question from the question and choices alone. Write that answer down before reading `source_answers`.
2. Read `source_answers`, then decide.
3. Use model knowledge, plus WebSearch and WebFetch on Google Cloud documentation only. List in `refs` only pages fetched in this session.
4. Always pick an answer, with `confidence` `high`, `medium` or `low` and a one-line `note`. Return `unusable` with a reason only for a broken question.
5. Explanations: when the decided answer equals `stored`, write only the choices that lack one. When it differs, or `stored` is empty, write every choice except those whose explanation is `by: user`. A user `Why:` line is never rewritten (D383). Style in [Explanation style](#explanation-style).
6. List in `why_conflicts` each letter whose user explanation contradicts the decided answer, for example one that says "Correct" on a choice decided wrong (D385).

Result `batches/answers/<batch_id>.json`:

```json
{"batch_id": "answers-0007", "step": "answers", "results": [
  {"id": "q_3fa9c21b07de", "status": "ok", "answer": ["A", "C"],
   "confidence": "medium", "note": "Site said B; Dataflow docs show A,C.",
   "refs": ["https://cloud.google.com/dataflow/docs/concepts/streaming-pipelines"],
   "explanations": {"A": "Correct. ...", "B": "Incorrect. ...", "C": "Correct. ..."},
   "why_conflicts": []},
  {"id": "q_0b1c2d3e4f5a", "status": "unusable", "reason": "Choice C text cut off."}
]}
```

Validation, per question. A rejected question requeues, the rest apply:

- ID in the **Batch**.
- Answer non-empty, letters within the row's choices.
- When the stem matches "choose N" or "select N" (digit or word, any case), exactly N letters.
- Confidence in the enum.
- Every choice has an explanation after apply.
- Each `why_conflicts` letter is a choice whose explanation is `by: user`.
- The [cell text rule](#cell-text-rule) holds.
- Every ref passes the [doc host rule](#doc-host-rule).
- `unusable` has a reason.

Apply on `ok`:

- Sets `answer`, `answer_by: llm`, `answer_confidence`, `answer_note`, `answer_refs`, `answer_checked_at`, the returned explanations with `explanation_by: llm` per choice, and `updated_at`.
- `low` confidence on a row that had no stored answer sets `uncertain` TRUE.
- `uncertain` stays TRUE on a row that had it. The `uncertain` value and the source answers remain as evidence (D32).
- User ticks: on a row with `answer_by: user` and no `unsure`, the ticks stay. When the LLM answer differs, `uncertain` becomes TRUE, the LLM view goes into `answer_note`, `answer_by` stays `user`, and the session's explanations are discarded so step 8 writes them for the kept answer `[G20]`. `answer_checked_at` is set either way. With `unsure` true the LLM answer replaces the ticks and `answer_by` becomes `llm`.
- Returned text for a choice whose explanation is `by: user` is discarded, not rejected.
- `why_conflicts` not empty: the user text stays, `uncertain` becomes TRUE, and `answer_note` gains "Your Why: on X contradicts this answer." The user fixes the md file.

Apply on `unusable`: `status: retired`, reason logged.

There is no second-opinion session in v1. The **Report** re-check is the second look.

Done when no `active` row is pending for `answers`, or the only pending rows sit in `failed` **Batches** listed in `state.md`.

### Explanation style

Decisions: D12, D13, D42, D104, D106.

One explanation per choice, 1 to 3 sentences, starting "Correct." or "Incorrect.", naming the Google Cloud fact that decides it. A doc URL appears only when the session fetched that page. This style binds `answers`, `explanations`, `augment` and `recheck`.

### Doc host rule

Decisions: D97, D110, D135.

A ref or link passes when its scheme is `https` and its host is `cloud.google.com` or ends in `.cloud.google.com` `[G8]`. The same rule checks **Study guide** links.

## Step 8: explanations

Decisions: D13, D57, D104 to D112. Ticket 13.

Runs on the shared dispatch. Pending row: see [Step status](#step-status). Worker `workers/explanations.md`, agent type `exam-bank-researcher`, task `explanation_writing`.

Input: the `answers` input shape, with `answer` and the existing explanations inside each question object, and each source's `explanation_blocks`. Worker rules: write an explanation for every choice that lacks one, in the [explanation style](#explanation-style); leave the answer as given; return `doubt` with a reason when the answer looks wrong.

Result: `{batch_id, step, results: [{id, status, explanations, refs, reason}]}`, status `ok` or `doubt`.

Validation: the `answers` checks that apply (ID, coverage of every choice, cell text, doc host, a reason on `doubt`).

Apply:

- `ok`: explanations with `explanation_by: llm` per written choice, row `explanation_by`, `updated_at`.
- `doubt` on a row without `answer_checked_at`: `uncertain` TRUE, so the row is pending for `answers` again, and the returned explanations are discarded. This happens once, since `answers` sets the mark.
- `doubt` on a checked row: the explanations apply as on `ok`, and the reason is appended to `answer_note`.

A `doubt` result still carries an explanation for every choice that lacked one, written for the answer as given.

Done when every choice of every `active` row has an explanation.

## Step 9: augment

Decisions: D36, D75, D114 to D128. Ticket 14.

Opt-in, on the shared dispatch.

Opt-in and plan:

1. When `augment.opt_in` is unset, or the step is forced, `eb.py augment-plan <exam>` prints the gap table: **Subdomain**, active rows, target, planned new, and total planned against `max_created_per_run`.
2. The main session shows the table and asks once. The answer goes into `state.json`. "No" marks the step `skipped`.
3. On "yes" the script appends the plan to `batches/augment/manifest.json`. The plan is fixed from then on. Drops are not refilled, and a D69 reopen never reopens `augment`.

Gap rule `[G11]`:

- Target per **Subdomain** = `target_total` × **Section** weight ÷ sum of all weights ÷ **Subdomains** in that **Section**, rounded to the nearest integer, and never under `min_per_subdomain`.
- Gap = target minus `active` rows in that **Subdomain**, never under 0. `created` rows count as active rows.
- When the gaps total more than `max_created_per_run`, each gap is scaled by cap ÷ total and rounded by largest remainder.

Create **Batch**: one **Subdomain** × up to `batch_size` new questions, task `augmentation`, worker `workers/augment.md`, agent type `exam-bank-researcher`.

Input `batches/augment/<batch_id>.in.json`:

- **Subdomain** number and title, and the count to create.
- Up to 5 example rows from the same **Subdomain**: `active`, not `created`, and either checked or not an **Uncertain answer**. Rows with source explanations come first. The pick is seeded by the **Batch** id. A **Subdomain** with none takes examples from its **Section**.
- Every existing stem in the **Subdomain**.
- The **Subdomain**'s choice-count mix and multi-select share.

Worker rules: each new question tests a fact or scenario that no existing stem tests; scenario stems like the examples; match the choice-count mix and multi-select share; explanations in the [explanation style](#explanation-style); at least one fetched doc ref per question.

Create result, per question: `{key, status, question, choices: [{text, explanation}], answer, subdomain, derived_from, confidence, note, refs, reason}`. `key` is a temp key unique in the file. Status `ok` or `unusable`.

Create validation: the `answers` checks, plus 2 to 6 choices, `subdomain` equal to the **Batch**'s, `derived_from` within the input example IDs, at least one ref. Rejected questions requeue.

Verify **Batch**: each valid create result gets one `verify` manifest entry. It uses `workers/answers.md`, the `answers` input and result shapes, and task `answer_filling`. Its input holds the created questions with no creator answer and no creator explanations, and an empty `source_answers`. Explanations a verify session writes are discarded `[G10]`.

- Kept: the verify answer equals the creator's and verify confidence is not `low`. Kept `answer_confidence` is the lower of the two.
- Dropped: anything else. Drops are counted in `state.md` only.

Entry: kept questions go to `sources/created.jsonl` as complete rows: `lineage: created`, `answer_by: llm`, `explanation_by: llm`, `answer_checked_at` set, `uncertain` FALSE, `derived_from` set, `subdomain_by: llm`. Source record: `name: created`, `url: batches/augment/<batch_id>.json#<key>`, `site_answer` = the checked answer, `scraped_at` = creation time. The script then runs [merge](#step-5-merge) on that file. No earlier step reopens.

Done when every `create` and `verify` entry has a valid result and `created.jsonl` is merged.

## Step 10: export

Decisions: D29, D34, D41, D148, D179, D212, D224, D319. Ticket 09.

A script step with no LLM. `eb.py export <exam>`:

1. Refuses when an `active` row has an empty answer, an empty `subdomain`, or a filled choice without an explanation. It prints the first 20 IDs with the missing part and writes nothing.
2. Writes `export/<slug>-questions.csv` per the [CSV contract](#csv-contract), overwriting the old file. All rows go out, `retired` ones included.
3. Rewrites `bank_meta.json`.
4. Prints: active and retired counts, **Uncertain answer** count, the line `section_weights: 1:13,2:16,3:21,4:20,5:18,6:13` built from the exam YAML for pasting into the app's Settings, and the text of `templates/import-steps.txt` `[G6]`.

The export writes no `Settings` tab and no other file (D148).

Stale rule: `eb.py state` renders the CSV and `bank_meta.json` in memory with the export code, `exported_at` left out, and compares bytes with the files. A missing file or any difference makes `export` pending, with N = the count of `id`s whose row differs. `/exam-bank <exam>` runs `export` once no earlier step is pending.

`templates/import-steps.txt`, wording from D209. The app spec owns this wording, and a change there is copied here:

```
Import into the sheet:
1. Open the spreadsheet and select the Questions tab.
2. File > Import > Upload, pick export/<slug>-questions.csv.
3. Import location: "Replace current sheet". Never "Replace spreadsheet".
4. Separator type: Comma.
5. Untick "Convert text to numbers, dates, and formulas".
```

Done when both files exist and the render matches them byte for byte.

## Study guide route

Decisions: D14, D129 to D145. Ticket 15.

`/exam-bank <exam> study-guide [<subdomain>] [redo]` writes one chapter per run. It is outside `dispatch.md`.

1. `eb.py study-guide-plan <exam> [<subdomain>] [redo]` rebuilds `study_guide_state.md` and picks the **Subdomain**. With none named it takes the first `ready` one in guide order. Naming a `blocked` one stops with the reason. Naming one that has a chapter stops unless `redo` is given.
2. The script writes `batches/study-guide/<subdomain>.in.json`: **Subdomain** number and title, the full list of its `active` IDs, then each fed row with choices, answer, explanations and a mark on **Uncertain answer** and `low` confidence rows. All **Lineages** feed. Over `study_guide.max_questions` it takes a seeded sample, non-`created` rows first.
3. The main session spawns one subagent: worker `workers/study-guide.md`, agent type `exam-bank-researcher`, task `study_guide_chapter`. It writes the chapter to its final path.
4. `eb.py study-guide-check <exam> <subdomain>` validates the chapter. An invalid chapter is deleted and the subagent runs again, up to two retries. After that the run reports the failure and the **Subdomain** stays `ready`.

Gate: a **Subdomain** is `blocked` while it has rows pending for `tag`, `answers` or `explanations`. `export` is not required.

Chapter:

- Path `exam-bank/<slug>/study-guide/<subdomain>-<title-slug>.md`. The slug is the title lowercased, every run of non-alphanumerics turned into one hyphen, ends trimmed. Example: `2.1-exploring-and-preprocessing-data-for-ml.md`.
- YAML front matter: `exam`, `subdomain`, `title`, `guide_version`, `question_ids` (the fed IDs), `written_at`, `model`.
- Headings in this order: Scope, Key concepts, Decision table, Traps, Question map, References. Key concepts covers each service: what it is, when to pick it, limits, closest alternative. Decision table has scenario cue, choice, why. Question map links concepts to question IDs.
- 1,500 to 3,000 words.
- Paraphrase scenarios and cite question IDs. Question and choice text is never copied.
- No claim rests only on marked rows.
- Web use and links follow the [doc host rule](#doc-host-rule), links only to fetched pages.

The check rejects: missing or wrong front matter; a heading missing or out of order; a cited ID not in the input; a URL failing the doc host rule; under 1,200 or over 3,500 words; a run of 12 or more words shared with an input stem or choice.

`study_guide_state.md`, beside `state.md`, rebuilt by script on every run, the only index:

```
# Study guide: pmle (guide 2026-06-01), 1 of 14 chapters done

- [x] 2.1 Exploring and preprocessing data for ML | 34 Qs | done 2026-11-16 | `/exam-bank pmle study-guide 2.1`
- [ ] 3.1 Building models given the task considering cost, complexity, latency, and scalability | 22 Qs | blocked: 5 pending answers | `/exam-bank pmle study-guide 3.1`
- [ ] 4.2 Scaling online model serving | 80 of 112 Qs | stale: +9 changed | `/exam-bank pmle study-guide 4.2 redo`
```

Status is `ready`, `blocked: <reason>`, `done` or `stale: <reason>`. A chapter is `stale` when the **Subdomain**'s `active` ID list differs from the list in its input file, or an `active` row in the **Subdomain** has `updated_at` later than `written_at`.

Done when the chapter passes the check and `study_guide_state.md` shows it `done`.

## Recheck route

Decisions: D23, D103, D216 to D226, D384, D386. Ticket 22.

`/exam-bank <exam> recheck` runs once per invocation on the shared dispatch, with manifest and results in `batches/recheck/`. It never reopens a main step.

1. `eb.py batches <exam> recheck` reads the newest `*.csv` in `reports/` by modified time. Columns, by header name: `report_id`, `reported_at`, `question_id`, `note`, `question_updated_at`, `status`, `resolved_at`, `resolution`.
2. A **Report** is pending when its `status` is `open`, its question exists and is `active`, and `reported_at` is later than the row's `rechecked_at`. Unknown and retired IDs are skipped and listed. A rerun on the same file finds nothing.
3. **Batches** form from the pending question IDs at the `report_recheck` `batch_size`.

Worker: `workers/answers.md`, the `answers` input and result shapes, task `report_recheck`. The input adds one section, `report_notes`, mapping question ID to the user's note. The worker reads it last, after its blind answer and the source answers. On a confirm it also rewrites any explanation the note shows to be wrong. A `by: user` explanation is never rewritten, on a confirm or an overturn, and `why_conflicts` works as in step 7 (D383, D385). It returns question text and choices untouched, and names a text problem in `note`.

Apply, on top of the [answers apply](#step-7-answers):

| Outcome | Changes | `uncertain` | `recheck_note` starts |
|---|---|---|---|
| confirm | check mark, any rewritten explanation. `answer_by` becomes `llm`, except on a user row, where it stays `user` | FALSE when confidence is `high`, else unchanged | `Confirmed.` |
| overturn | answer, every explanation not `by: user` | TRUE | `Changed from X to Y.` |
| `unusable` | `status: retired` | unchanged | `Retired.` |
| row with `answer_by: user`, LLM differs | nothing in answer or explanations | TRUE | `Kept your answer X. The re-check suggests Y.` `[G16]` |

- `rechecked_at` is set on every outcome.
- `recheck_note` is one line of plain text, at most 300 characters: the prefix, then the worker's note or reason.
- `updated_at` moves only when answer or explanations changed.
- On a user row the user edits the md file, since the next `merge` would undo an overwrite.

The route ends by printing `/exam-bank <exam> export` and the text of `templates/import-steps.txt`. How the app resolves a **Report** from `rechecked_at` is in 0002.

Done when every pending **Report** row has `rechecked_at` later than its `reported_at`, or sits in a `failed` **Batch**.

## Workers

Decisions: D65, D71, D72, D107, D108, D218, D249. ADR 0004.

Each worker file holds only the rules of its section above, plus this shared frame: read the input file named in the prompt, write one JSON result file, reply with one line.

| Worker file | Agent type | Used by | Result shape defined in |
|---|---|---|---|
| `llm-scrape.md` | `exam-bank-reader` | `llm-scrape` | [Step 3](#step-3-llm-scrape) |
| `tag.md` | `exam-bank-reader` | `tag` | [Step 6](#step-6-tag) |
| `answers.md` | `exam-bank-researcher` | `answers`, `augment` verify, `recheck` | [Step 7](#step-7-answers) |
| `explanations.md` | `exam-bank-researcher` | `explanations` | [Step 8](#step-8-explanations) |
| `augment.md` | `exam-bank-researcher` | `augment` create | [Step 9](#step-9-augment) |
| `study-guide.md` | `exam-bank-researcher` | `study-guide` | [Study guide route](#study-guide-route) |

Agent definitions in `.claude/agents/` `[G9]`: `exam-bank-reader` has `tools: Read, Write`. `exam-bank-researcher` has `tools: Read, Write, WebSearch, WebFetch`. Neither lists the Agent tool, and neither sets `model` or `effort`, since each call passes both. A subagent cannot preload this skill because of `disable-model-invocation`, so each one reads its worker file itself.

## Scripts

Decisions: D62, D63, D77, D95, D239, D242. ADR 0002, ADR 0004.

One entry point, `python .claude/skills/exam-bank/scripts/eb.py <command> <exam> [args]`. Each command prints plain text for the main session and exits non-zero on a stop.

| Command | Does |
|---|---|
| `state [step]` | reruns setup checks 1 to 3, rebuilds `state.md`, prints the step to run, its step file, the summary and the next command |
| `setup` | [Step 1](#step-1-setup) |
| `scrape` | [Step 2](#step-2-scrape) |
| `fetch` | the fetch part of [Step 3](#step-3-llm-scrape) |
| `intake` | [Step 4](#step-4-intake) |
| `merge [file]` | [Step 5](#step-5-merge), all sources or one file |
| `batches <step>` | forms **Batches**, writes inputs, prints the dispatch list. For `llm-scrape` it runs `fetch` first |
| `apply <step>` | validates and applies result files, requeues, prints the next list |
| `augment-plan [yes\|no]` | prints the gap table, or records the answer and writes the plan |
| `export` | [Step 10](#step-10-export) |
| `study-guide-plan`, `study-guide-check` | [Study guide route](#study-guide-route) |

Writes to `bank.jsonl`, `state.json` and manifests go through a temp file and a rename. Only `merge` and `apply` write `bank.jsonl`.

`eb.py` parses arguments and calls one module per concern, all in `scripts/`: `ids` (norm and ID), `intake`, `fetch`, `merge`, `batches` (forming and `apply`), `validate` (result-file and cell-text checks), `export`, `state`, `study_guide`. Each scraper in `scrapers/` exposes `parse_page(html: str, url: str) -> list[dict]`, kept apart from its Playwright driver.

## Tests

pytest under `.claude/skills/exam-bank/scripts/tests/`. `pytest` goes in a root `requirements-dev.txt`, so `requirements.txt` keeps its four packages. Fixture tests:

- `ids`: golden `norm` and ID vectors for the [ID rules](#id-rules), frozen by ADR 0001.
- Each scraper's `parse_page` on saved HTML in `tests/fixtures/<site>/`.
- `intake` on `templates/given-example.md`.
- `merge` on fixture `sources/*.jsonl` against an expected `bank.jsonl`, reruns included.
- `apply` per step on hand-written good and bad result files.
- `export` byte for byte against a golden CSV and `bank_meta.json`.
- `study-guide-check` on a good and a bad chapter.

Workers have no automated test. Each worker gets one fixture `.in.json` in `tests/fixtures/workers/` for a manual run.

## CSV contract

Decisions: D15, D16, D26 to D48, D99, D205, D207, D211, D212, D219. ADR 0001, ADR 0003. Ticket 09, amended by 22.

The file `exam-bank/<slug>/export/<slug>-questions.csv` is the only thing the skill hands the app. The app's own checks on it are in 0002.

### File format

`[G12]`

- UTF-8, no byte order mark.
- RFC 4180: comma separator, `"` quote, quotes doubled inside a cell, a cell quoted only when it holds a comma, a quote or a line break. Python `csv.writer` defaults with `lineterminator="\r\n"`.
- Rows end in CRLF. A line break inside a cell is LF.
- Row 1 is the header. Then one row per question, in `bank.jsonl` order.
- An empty value is an empty cell.

### Columns

30 columns, in this order, with these exact header names:

| # | Column | Values | Filled |
|---|---|---|---|
| 1 | `id` | `q_` + 12 lowercase hex | always |
| 2 | `exam` | exam slug | always |
| 3 | `status` | `active`, `retired` | always |
| 4 | `subdomain` | guide number as text, for example `2.1` | always on `active` |
| 5 | `subdomain_title` | title from the exam config | with `subdomain` |
| 6 | `question` | plain text | always |
| 7 | `choice_a` | plain text, no letter prefix | always |
| 8 | `choice_b` | plain text | always |
| 9 | `choice_c` | plain text | when the question has 3 or more choices |
| 10 | `choice_d` | plain text | 4 or more |
| 11 | `choice_e` | plain text | 5 or more |
| 12 | `choice_f` | plain text | 6 |
| 13 | `answer` | letters, see below | always on `active` |
| 14 | `explanation_a` | plain text | on `active`, when `choice_a` is filled |
| 15 | `explanation_b` | plain text | same, for b |
| 16 | `explanation_c` | plain text | same, for c |
| 17 | `explanation_d` | plain text | same, for d |
| 18 | `explanation_e` | plain text | same, for e |
| 19 | `explanation_f` | plain text | same, for f |
| 20 | `lineage` | `scraped`, `given`, `created` | always |
| 21 | `sources` | source names, one per line | always |
| 22 | `source_urls` | one per line, same order as `sources` | always |
| 23 | `source_answers` | `name: letters`, one per line | when a source gave an answer |
| 24 | `uncertain` | `TRUE`, `FALSE` | always |
| 25 | `answer_by` | `source`, `user`, `llm` | always on `active` |
| 26 | `explanation_by` | `source`, `user`, `llm` | always on `active` |
| 27 | `derived_from` | question IDs, one per line | on `created` rows |
| 28 | `updated_at` | `YYYY-MM-DDTHH:MM:SSZ` | always |
| 29 | `rechecked_at` | `YYYY-MM-DDTHH:MM:SSZ` | after a re-check |
| 30 | `recheck_note` | one line, at most 300 characters | after a re-check |

Columns 29 and 30 sit at the end `[G12]`.

Header row:

```
id,exam,status,subdomain,subdomain_title,question,choice_a,choice_b,choice_c,choice_d,choice_e,choice_f,answer,explanation_a,explanation_b,explanation_c,explanation_d,explanation_e,explanation_f,lineage,sources,source_urls,source_answers,uncertain,answer_by,explanation_by,derived_from,updated_at,rechecked_at,recheck_note
```

Not columns: the number of answers to select (count the letters in `answer`), a general explanation, the schema version, any confidence or note field other than `recheck_note`, any app data.

### ID rules

`[G13]` D16 names what is normalized. The algorithm below is confirmed, and ADR 0001 freezes it for good at the first merge.

- Format: `q_` + the first 12 hex characters of a SHA-256 digest, lowercase. The prefix keeps the cell a string in Sheets.
- `norm(text)`:
  1. Unicode NFKC.
  2. `str.casefold()`.
  3. For a choice only: strip one leading letter prefix matching `^\s*\(?[a-f][\.\):]\s+`.
  4. Delete every character whose Unicode category starts with `P`, and every backtick.
  5. Turn each run of whitespace into one space, then trim.
- Hash input: `norm(question)`, a line feed, then the `norm` of each choice sorted ascending and joined by line feeds, encoded as UTF-8.
- The ID is computed once, when the question first enters `bank.jsonl`, then stored and never recomputed. A row's ID may stop matching the hash of its current text. That is expected and stays as it is.
- Sorting the choices makes a reordered copy the same question.
- Dedupe compares an incoming hash with every stored `id` and with the hash of every row's current text.
- IDs are unique in the file. A row is never deleted and an ID is never reused. A question that should go away gets `status: retired`.
- A question has 2 to 6 choices. One with more is skipped at its source step.

The app keys every tab on `id`, so these rules bind 0002 as well.

### Answer letters

- Letters are uppercase `A` to `F`. `A` means `choice_a`, and so on. They point into the stored choice order, which is the order of the first source that brought the question.
- `answer` holds 1 or more letters, sorted ascending, joined by a comma with no space: `B` or `A,C`.
- Every letter in `answer` points to a filled choice.
- A multi-select question is one with more than one letter. Scoring is all or nothing (D9), and is the app's job.
- `source_answers` uses the same letter frame. `merge` remaps each source's letters into the stored order first. One line per source that gave an answer: `examtopics: B`. A community answer gets its own line under `<name>-community`: `examtopics-community: A,C`.
- A `given` row's source line is `given: A,C`, with URL `given/<file>.md#<key>`. A `created` row's is `created: B`, with URL `batches/augment/<batch_id>.json#<key>`.

### Guarantees to the app

The export code holds these on every file it writes:

- The 30 headers, exact names, this order.
- Every `id` filled and unique.
- `status` is `active` or `retired`.
- On every `active` row: `subdomain`, `subdomain_title`, `answer`, `answer_by`, `explanation_by` filled, and one explanation per filled choice.
- Choices fill from `choice_a` with no hole.
- Cell text follows the [cell text rule](#cell-text-rule).
- Every cell is text. The import must run with "Convert text" off so `2.10`, IDs and timestamps stay strings (D207).

A `retired` row may have empty answer, explanation and **Subdomain** cells.

## Permissions printed by setup

Decisions: D70, D97, D249, D328. Research: `claude-skill-mechanics.md` line 66.

Background subagents raise a permission prompt for any tool that is not pre-allowed. `setup` prints this block and tells the user to merge it into `.claude/settings.local.json`. It is the only copy. The README points here by telling the reader to paste what `setup` prints `[G8]`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python .claude/skills/exam-bank/scripts/eb.py *)",
      "Read(/.claude/skills/exam-bank/**)",
      "Read(/exam-bank/**)",
      "Edit(/exam-bank/**)",
      "WebSearch",
      "WebFetch(domain:cloud.google.com)",
      "WebFetch(domain:docs.cloud.google.com)"
    ]
  }
}
```

WebSearch takes no domain limit in a permission rule. The limit on it is the worker rule plus the [doc host rule](#doc-host-rule) on refs. The `exam-bank-reader` agent type keeps `llm-scrape` and `tag` workers off the web.

## README parts

Decisions: D18, D322 to D329, D332 to D340. Visual layer: D1 to D37 of the [readme-visuals interview log](../../.scratch/readme-visuals/interview-log.md), cited below as RV-Dn.

The last build task assembles the root `README.md`. This spec owns the Showcase, the Intro, Prerequisites, Part 1, the skill side of Upkeep and Troubleshooting, Notes and License. 0002 owns the app visuals, the Try it path, Part 2 and the app side of Upkeep and Troubleshooting (RV-D22).

Rules for every part:

- Two layers (RV-D5). The Showcase is for any visitor. Everything below the table of contents is for a reader at home in a terminal, git, Python and Claude Code, with a Google account.
- Below the Showcase, the README repeats only what the reader types, clicks or edits. Every rule, schema and algorithm is a link to a section of this spec or 0002.
- Images are allowed (RV-D1), under the [visual rules](#visual-rules). Still no step rules, no CSV schema, no per-source scraping detail, no FAQ, no contributing guide.
- The README names no question site. Sources appear only in the example config.
- Shell commands are given for bash, with the PowerShell form beside any that differs.
- Upkeep, Troubleshooting and every PowerShell variant sit in `<details>` blocks (RV-D19).

### Visual rules

- Every app image comes from the **Demo bank** at `docs/demo/demo-bank.csv`, never from a real bank (RV-D2). The Demo bank is specified in [0002, Demo bank](0002-study-app.md#demo-bank).
- Before an image enters the repo, mask the email, Google avatar, sheet ID, script ID, `/exec` URL, question-site names and local paths (RV-D3, RV-D24). Mask with a solid fill, never a blur.
- The agent makes every image. The user captures nothing and only approves tool access, OAuth clicks and outward actions (RV-D27).
- All images live in `docs/assets/`. A GIF is at most 960 px wide, 15 s long and 3 MB. PNGs are optimized (RV-D12).
- App images are made by the committed capture tool, so one command refreshes them (RV-D7, RV-D8). The tool is specified in [0002, Visuals, app side](0002-study-app.md#visuals-app-side).

### 0 Showcase

Top of the README, in this order (RV-D17):

1. Title, then badges: License MIT, `Checks` CI status, "Claude Code skill", "Google Apps Script" (RV-D13).
2. Tagline: "Build your own Google Cloud certification question bank with Claude Code, then drill it in a free Google Sheets exam simulator." (RV-D20)
3. Hero GIF, from 0002.
4. Legal line: "Personal use only · Not affiliated with Google · [details](#7-notes-and-license)" (RV-D15).
5. Feature grid of four tiles, from 0002.
6. How it works: a Mermaid diagram, sources → the 10 steps → CSV → Sheet app, and `docs/assets/export-summary.png`, the real `export` summary as a terminal-style image (RV-D10, RV-D28). A committed script runs `eb.py export <exam>`, masks question-site names and local paths in the text, and renders the image with Playwright. Masking happens on text, before rendering.
7. Try it in 5 minutes, from 0002.
8. Star line: "If this helps you pass, a ⭐ helps others find it." (RV-D21)
9. Table of contents, then section 1.

Social preview: `docs/assets/social-preview.png`, 1280×640. The build drafts the repo About text and topics. After the user's yes in chat, the agent sets About and topics with `gh repo edit` and uploads the image in GitHub Settings through Claude in Chrome, on the public repo (RV-D14, RV-D31).

### 1 Intro

Three sentences: what the project does, the two parts ("Build the **Question bank**", "Deploy the study app"), and one line that the bank is for personal use.

### 2 Prerequisites

- Claude Code with access to the aliases in `models.yaml` (opus, sonnet).
- git.
- Python 3.11 or newer.
- Node 22 or newer and `npm i -g @google/clasp`.
- A Google account with the Apps Script API on, at script.google.com/home/usersettings.

Closing cost line: a full build runs many opus subagent sessions for answers, explanations, augmentation and re-checks; usage grows with bank size; lower it through the aliases and effort in `models.yaml`.

### 3 Part 1: Build the Question bank

Install:

```bash
git clone <this repository's URL>
cd <the cloned folder>
pip install -r requirements.txt
playwright install chromium
```

The clone URL is filled in at assembly `[G19]`. Then: open Claude Code in the folder.

Config:

```bash
mkdir -p exam-bank/config/exams
cp .claude/skills/exam-bank/templates/models.example.yaml exam-bank/config/models.yaml
cp .claude/skills/exam-bank/templates/exams/pmle.example.yaml exam-bank/config/exams/pmle.yaml
```

```powershell
New-Item -ItemType Directory -Force exam-bank/config/exams
Copy-Item .claude/skills/exam-bank/templates/models.example.yaml exam-bank/config/models.yaml
Copy-Item .claude/skills/exam-bank/templates/exams/pmle.example.yaml exam-bank/config/exams/pmle.yaml
```

Keys the reader may edit: `enabled` per source, `alias` and `effort` per task. One line: read each source's terms before you leave it enabled. Link to [Config](#config).

Permissions: run `/exam-bank pmle`, then paste what `setup` prints into `.claude/settings.local.json`.

Run: start a fresh session, run `/exam-bank pmle`, read the summary, run the next command it prints, and repeat until `export` is done. Then this table:

| Step | What it does | What you do |
|---|---|---|
| `setup` | checks config and tools | paste the printed permissions |
| `scrape` | reads the **Curated sites** | log in and solve any CAPTCHA in the browser window it opens |
| `llm-scrape` | reads the other source pages | nothing |
| `intake` | reads your own questions | write them in `exam-bank/pmle/given/*.md`, format in `templates/given-example.md` |
| `merge` | removes duplicates, assigns IDs | nothing |
| `tag` | sets each question's **Subdomain** | nothing |
| `answers` | fills missing answers and every **Uncertain answer** | nothing |
| `explanations` | writes an explanation per choice | nothing |
| `augment` | creates questions for thin **Subdomains** | answer yes or no to the gap table, once |
| `export` | writes the CSV | import it, Part 2 |

One line on the **Study guide**: `/exam-bank pmle study-guide`, with a link to [Study guide route](#study-guide-route). The CSV path: `exam-bank/pmle/export/pmle-questions.csv`.

Section 4, Part 2 "Deploy the study app", is specified in 0002.

### 5 Upkeep, skill side

- Re-check **Reports**: in the sheet open the `Reports` tab, File > Download > Comma-separated values, save into `exam-bank/<slug>/reports/`. Run `/exam-bank <slug> recheck`, then `/exam-bank <slug> export`, then import. The import steps are a link to Part 2, with no second copy.
- Update the skill: `git pull`.
- Add another exam, skill half: copy `templates/exams/pmle.example.yaml` to `exam-bank/config/exams/<slug>.yaml`, fill it from the official exam guide (**Subdomains**, **Section** weights, sources), run `/exam-bank <slug>`.

### 6 Troubleshooting, skill side

One line each, message then fix, with a link to the named section:

- `setup` stops on a set environment variable or a missing tool: unset the variable or install the tool, rerun. [Step 1](#step-1-setup).
- `state.md` shows `waiting on user`: do the action it names, rerun the command. [Step 2](#step-2-scrape).
- `failed` **Batches**: run the same command again. A question that validation rejects in two such runs is retired and listed in `state.md`. [Dispatch](#dispatch).
- A source shows `failed: robots` or another reason: put those questions in `given/`. [Step 3](#step-3-llm-scrape).

### 7 Notes and License

- The bank is for personal use. Never publish the CSV, the sheet or `exam-bank/`.
- Read each source's terms of service before you enable it. Fetching obeys `robots.txt`.
- No script bypasses a CAPTCHA. You solve it.
- LLM-written answers can be wrong. Mind an **Uncertain answer** and use **Report**.
- Not affiliated with Google. Exam names and guide text belong to their owners.
- License: MIT, see `LICENSE`.

## Confirm at build

Decisions: D202, D214, D339. Ticket 19 comment, tickets 01 and 02, research `claude-skill-mechanics.md` lines 61 and 72.

A result here changes text or a selector, never a decision. Skill side:

1. ExamTopics selectors, the page-count line, and whether the answer and the "Most Voted" tag are in the DOM without a click (ticket 01).
2. CertSafari: whether answers and explanations sit in the static HTML, and its selectors (ticket 02).
3. Whizlabs, TheServerSide and Open Exam Prep: whether the question text sits in the static HTML. Only MockingOwl was confirmed (ticket 19).
4. An Agent call with a custom `subagent_type` honours the per-call `model` and `effort`, checked in a transcript. Passing them is done by the model, so verify it happens.
5. `$ARGUMENTS` reaches `SKILL.md` as written, and the Read-based router loads only one step file.
6. The permission rule syntax in [Permissions printed by setup](#permissions-printed-by-setup) silences prompts for background subagents, path forms included.
7. Whether Google Cloud docs now answer from `docs.cloud.google.com`, which decides if the second WebFetch line is needed.
8. The `python` command name on the user's platform, used in the allow-list and by the router.
9. The repository URL for the README clone line `[G19]`.
10. Whether Google's official sample-question form shows the correct answers after submit. If not, every typed-in sample question carries `Unsure: yes` (D382).

App side, owned by 0002 and listed in D339: the clipboard fallback and its Ctrl+C line, the three Sheets import checks of D214, the unverified-app and web-app access wording, and clasp `create-script` against a local `appsscript.json` and `--project`. Line 5 of `import-steps.txt` uses the "Convert text" wording that D214 confirms.

## Decision gaps

The user settled every mark on 2026-11-17. Rationale in `.scratch/gcp-exam-sim/interview-log.md`.

| Mark | Decision |
|---|---|
| G1 | D341 |
| G2 | D342 |
| G3 | D343 |
| G4 | D344 |
| G5 | D345 |
| G6 | D346 |
| G7 | D347 |
| G8 | D348 |
| G9 | D349 |
| G10 | D350 |
| G11 | D351 |
| G12 | D352 |
| G13 | D353 |
| G14 | D354 |
| G15 | D355 |
| G16 | D356 |
| G17 | D357 |
| G18 | D358 |
| G19 | D359 |
| G20 | D360 |
| G21 | D361 |

A later spec review settled eight more points, D379 to D387, cited by D-number where they apply: `mock_test` and `row_count` removed (D379), one Prerequisites list here (D380), auto-retire (D381, D386, D387), Google's sample questions through `given/` (D382), user `Why:` lines kept (D383, D385), `uncertain` TRUE when a re-check disputes a user answer (D384).
