# 0002: study app

Status: shipped
Reviewed: 2026-11-17

Build-ready spec for the Apps Script study app. The app runs over one Google Sheet per exam, reads the **Question bank** the skill exports ([0001](0001-exam-bank-skill.md)), and offers **Review mode** and the **Mock Test**.

Sources: decisions D6 to D9, D12, D17, D18, D23, D28, D32, D39, D42, D146 to D226, D254 to D265, D268 to D340, D346, D362 to D378, D388 to D393 in `.scratch/gcp-exam-sim/interview-log.md`, ADR 0001 and ADR 0003 in `docs/adr/`, vocabulary in `GLOSSARY.md`, the three prototypes in `.scratch/gcp-exam-sim/prototypes/`.

## How to read this spec

- Each section opens with a `Decisions:` line naming the D-numbers and ADRs it rests on.
- A mark like `[G3]` means no D-number covered the point, or two disagreed. The user settled every one on 2026-11-17, and the text beside the mark is the decision. [Decision gaps](#decision-gaps) maps each mark to its D-number.
- Items a live check must settle are in [Confirm at build](#confirm-at-build).
- Each rule appears once. Other sections link to it.
- Where a ticket body and a later decision disagree, this spec follows the later decision. Tickets 16 and 21 still say 28 columns, ticket 25 still says "no Flags", and the review prototype still has an inline note panel and a draft prompt. All four are superseded.
- The prototypes are the reference for look and for UI strings this spec does not give. They are throwaway code. Do not copy their logic.

## Scope

Decisions: D2, D6, D18, D24, D144, D149, D177, D184, D204, D285, D320.

In scope: the app source in `app/`, the six app tabs, the checks on the `Questions` tab, **Review mode**, the **Mock Test** with results and history, the home and Settings screens, the app side of the **Report** re-check loop, Copy prompt, the Node tests, the app-owned README parts.

Out of scope: see [Out of scope](#out-of-scope).

One user per deployment. One spreadsheet per exam. App tabs carry no `exam` column. One code folder serves every exam sheet.

## Platform and layout

Decisions: D7, D18, D202, D210, D313, D322, D330, D331, D333. Ticket 06. Research: `.scratch/gcp-exam-sim/research/apps-script-app-form.md`.

The app is a script bound to the spreadsheet and deployed as a web app. It runs as the owner and only the owner can open it. The page is a full browser tab. A Sheets menu holds the link to it, since a menu item cannot open a full page itself.

```
app/
  appsscript.json        manifest
  server/*.js            server code, pushed as .gs
  client/*.html          one page: markup, styles and client script as HtmlService includes
  tests/*.test.js        Node tests, never pushed
  .claspignore           excludes tests/ and package.json
  package.json           one script: "test": "node --test tests/"
  .clasp.json            gitignored, holds the script ID
  .clasp-<slug>.json     gitignored, one per further exam
```

The file split inside `server/` and `client/` is the builder's call `[G1]`. These rules bind it:

- No npm dependency and no CDN script or stylesheet. Plain JavaScript on the V8 runtime, plain HTML and CSS.
- Server files load in Apps Script as global scripts and in Node through an export guard, so the same file runs in both.
- All sheet, property, lock, clock and random access goes through one adapter, see [Server interface](#server-interface).
- 0002 adds one line to the root `.gitignore`: `app/.clasp*.json`.

Manifest:

```json
{
  "timeZone": "Etc/UTC",
  "runtimeVersion": "V8",
  "exceptionLogging": "STACKDRIVER",
  "oauthScopes": [
    "https://www.googleapis.com/auth/spreadsheets.currentonly",
    "https://www.googleapis.com/auth/script.container.ui"
  ],
  "webapp": {"executeAs": "USER_DEPLOYING", "access": "MYSELF"}
}
```

The two scopes are the narrowest that should work. A live check confirms them, see [Confirm at build](#confirm-at-build). The manifest time zone is not used for dates. Dates use the spreadsheet's time zone, see [Dates and time](#dates-and-time).

### Menu

`[G2]` `onOpen` adds a menu named "Study app" with three items:

| Item | Does |
|---|---|
| Open study app | a small dialog with a link to the web app `/exec` URL, opening in a new tab. The URL is the one `doGet` saved in the script property `web_app_url` on the last page load, since `ScriptApp.getService().getUrl()` from a menu dialog returns a dead URL (Confirm at build, item 11). Before the web app has been opened once it says "Open the web app once from its URL first. See the README, Part 2, step 4." |
| Import bank | a dialog with the [import steps](#import-steps) |
| Rebuild study state | after a confirm, runs the [rebuild](#rebuild) |

### Limits that shape the code

- A server call may run 6 minutes. No call here comes near it.
- `google.script.run` passes JSON-like values only, never a `Date`. Every date crosses as a string.
- The client makes one `load` call at start and keeps the bank in memory. It reads no tab again until the next page load.
- `localStorage` is never the source of truth. The app does not use it.

## Sheet tabs

Decisions: D6, D146 to D164, D171, D179, D183, D190, D205, D260, D304, D318. ADR 0003. Tickets 16, 17, 21, 22, 24, 26, 27.

Seven tabs:

| Tab | Rows | Written by |
|---|---|---|
| `Questions` | the **Question bank**, 30 columns, see [0001, CSV contract](0001-exam-bank-skill.md#csv-contract) | File > Import only |
| `Settings` | `key`, `value` | app, or the user by hand |
| `QuestionState` | one per touched question | app |
| `Attempts` | one per graded answer, append-only | app |
| `MockTests` | one per **Mock Test** | app |
| `MockTestItems` | one per question of the unfinished **Mock Test** | app |
| `Reports` | one per **Report** | app |

Rules for every app tab:

- The app never writes to `Questions` (ADR 0003). It joins by `id` on every load and never relies on row order there.
- The app creates each app tab with its header row, sets the whole tab to plain-text format and freezes row 1.
- The app finds columns by header name. A column it does not know is left alone.
- Timestamps are ISO 8601 UTC, `YYYY-MM-DDTHH:MM:SSZ`, the same form as the bank. Two timestamps compare as strings.
- Booleans are the strings `TRUE` and `FALSE`.
- Letters are uppercase, comma-joined with no space, sorted ascending, and always point into the stored choice order of [0001, Answer letters](0001-exam-bank-skill.md#answer-letters).
- Each server call writes a tab in one batch call, never cell by cell.

### Settings

`key`, `value` rows. A new setting is a new row.

| Key | First value | Meaning |
|---|---|---|
| `exam_name` | asked at first open | full exam name, used in the home header and Copy prompt |
| `exam_date` | asked at first open | `YYYY-MM-DD` |
| `mock_question_count` | `50` | default question count of a **Mock Test** |
| `mock_minutes` | `120` | default minutes of a **Mock Test** |
| `section_weights` | asked at first open, may be empty | `1:13,2:16,...`. Empty means the bank's own proportions |
| `schema_version` | `1` | version of the app-tab layout. It says nothing about the bank |

Checks are in [Settings screen](#settings-screen).

### QuestionState

`question_id`, `box`, `due_at`, `attempts`, `correct_count`, `last_seen_at`, `last_result`, `bookmarked`, `note`, `note_updated_at`.

- The app creates a row on the first answer, **Bookmark** or note. No row means unseen.
- `box` is `0` for unseen, else `1` to `5`.
- `due_at` is a plain date `YYYY-MM-DD` in the spreadsheet's time zone, stored uncapped. Empty while `box` is `0`.
- `attempts` and `correct_count` count non-`skipped` attempts.
- `last_result` is `correct` or `wrong`.
- One note per question, at most 1,000 characters.
- `box`, `due_at`, the two counters, `last_seen_at` and `last_result` are a cache of `Attempts`. `bookmarked`, `note` and `note_updated_at` live only here.

### Attempts

`answered_at`, `question_id`, `mode`, `test_id`, `selected`, `correct_answer`, `result`, `question_updated_at`, `flagged`.

- `mode` is `review` or `mock`. `test_id` is empty in **Review mode**.
- `selected` holds the picked letters, empty on `skipped`.
- `correct_answer` is the bank's `answer` copied at grading.
- `result` is `correct`, `wrong` or `skipped`.
- `question_updated_at` is the bank row's `updated_at` at grading. It records which version was graded.
- `flagged` is `TRUE` or `FALSE` on a `mock` row, copied from the item at submit. Empty on a `review` row.
- The app appends rows and never edits, re-grades or deletes one.
- A **Mock Test** appends its rows in `position` order, so append order is test order.

### MockTests

`test_id`, `status`, `started_at`, `submitted_at`, `question_count`, `minutes_allowed`, `seconds_left`, `correct_count`, `score_pct`.

- `test_id` is `t_` + the UTC start time as `YYYYMMDDTHHMMSSZ`, for example `t_20261117T081500Z`. The compact form comes from the prototypes.
- `status` is `in_progress`, `submitted` or `discarded`. `in_progress` is the one unfinished status; a pause stores no status (D388).
- At most one row has `in_progress`.
- A discarded test keeps its row and has no `Attempts`.

### MockTestItems

`test_id`, `position`, `question_id`, `choice_order`, `selected`, `flagged`, `question_updated_at`.

- Holds the unfinished test only. Submit and discard clear the tab.
- `position` starts at 1.
- `choice_order` is the stored letters in display order with no separator `[G3]`. `CADB` shows stored choice C first.
- `selected` holds stored letters, never display letters.
- `question_updated_at` is the bank row's `updated_at` when the item was created or last reset.

### Reports

`report_id`, `reported_at`, `question_id`, `note`, `question_updated_at`, `status`, `resolved_at`, `resolution`.

- `report_id` is `r_` + the UTC creation time, same compact form as `test_id`.
- `status` is `open` or `resolved`.
- At most one `open` row per question.
- The skill reads this tab as a downloaded CSV and finds these eight columns by header name, see [0001, Recheck route](0001-exam-bank-skill.md#recheck-route). Do not rename one.

### Rows for missing and retired IDs

Decisions: D39, D162.

The app keeps every row whose `question_id` is missing from `Questions` or `retired` there. Past **Mock Test** scores stay. Those IDs are left out of the sampler, the **Review mode** filters and **Subdomain** weakness. An ID that comes back gets its history back.

An orphan ID is a question ID that appears in `QuestionState`, `Attempts`, `Reports` or `MockTestItems` and not in `Questions`. The orphan count is the number of distinct orphan IDs `[G4]`.

## Dates and time

Decisions: D155, D174, D190, D318.

- "Today" is the current date in the spreadsheet's time zone.
- A seen question's due date is the earlier of its `due_at` and the day before `exam_date`. The cap applies on read and is never stored. An exam-date edit takes effect at once with no rewrite.
- Once today is later than `exam_date` the cap is off.
- A question is due when it is seen and its due date is today or earlier.
- "N days left" is `exam_date` minus today. On the day itself the header reads "Exam is today". After it the header reads "Exam date passed · update in Settings".

## Load sequence

Decisions: D148, D180, D203, D208, D209, D213, D219, D317. ADR 0003. Ticket 21.

Every page load runs one `load` call. The server goes through these steps in order and stops at the first one that returns a screen:

1. **Wipe guard.** The "set up" mark exists and the `Attempts` tab is missing. Return the wipe screen. Create nothing.
2. **Tabs.** Create each missing app tab, and an empty `Questions` tab when it is missing. Then set the mark when it is absent.
3. **Layout version.** `Settings.schema_version` is filled and is not `1`. Return a stop screen `[G5]`.
4. **Bank check.** A refusal returns the refusal screen with the import steps.
5. **Settings check.** A bad or missing value returns the Settings screen with the field marked. On first open this is the same screen in setup mode.
6. **Half-finished submit.** Finish it, see [Submit](#submit).
7. **Reports.** Resolve them, see [Report loop](#report-loop).
8. Return the home screen data.

Steps 2, 5, 6 and 7 write under the script lock.

### The "set up" mark

`[G6]` The mark is the script property `setup_done_at`, holding the time step 2 first ran. A script property sits outside every tab, so an import cannot remove it.

| Mark | `Attempts` tab | Means | Step 2 does |
|---|---|---|---|
| absent | missing | first open | creates all tabs, sets the mark |
| absent | present | a copied sheet | creates any missing tab, sets the mark |
| present | present | normal | creates any missing tab `[G7]` |
| present | missing | "Replace spreadsheet" wiped the app tabs | never reached, step 1 stops |

When step 2 recreates `QuestionState` on a sheet that has `Attempts` rows, it runs the [rebuild](#rebuild) and the home screen shows a warn banner: "The QuestionState tab was missing. Boxes and due dates were rebuilt from your attempts. Bookmarks and notes could not be recovered."

Wipe screen text:

```
The app's tabs are gone. This happens when a bank is imported with "Replace spreadsheet".
Nothing is lost yet. In the spreadsheet, open File > Version history > See version history
and restore the version from before the import. Then import again with "Replace current sheet".
```

The screen has an "Open spreadsheet" link and nothing else.

### Layout version stop

`[G5]` v1 writes `schema_version` `1` and has no migration. Any other value stops with: "This sheet was set up by a different version of the app (layout N). Update the app code, see the README, Upkeep." An empty value is a Settings error, handled in step 5 by writing `1`.

## Bank check

Decisions: D203 to D207, D211, D212, D215, D219, D391. Ticket 21, amended by 22.

The app checks the `Questions` tab on every load. There is no "Validate" action and no snapshot of the previous bank. What the file promises is in [0001, Guarantees to the app](0001-exam-bank-skill.md#guarantees-to-the-app). A failure here means a damaged import, since `export` already refuses incomplete rows.

Refuse:

| # | Case | Message per row |
|---|---|---|
| 1 | `Questions` missing, or it has no header row or no data row | "The Questions tab is empty." |
| 2 | one of the 30 headers is missing, matched by exact name in any order | "Missing column: `<name>`" |
| 3 | an empty `id` | "Row N: empty id" |
| 4 | a duplicate `id` | "Row N: duplicate id `<id>`, first seen in row M" |
| 5 | a cell in `id`, `subdomain`, `answer`, `uncertain` or `updated_at` is not a string | "Row N: `<column>` is not text" |
| 6 | `status` is not `active` or `retired` | "Row N: status `<value>`" |
| 7 | an `answer` letter points to an empty choice, on an `active` row | "Row N: answer `<letter>` has no choice" |
| 8 | zero `active` rows | "No active questions." |

- One bad row refuses the whole bank. No study screen opens.
- Case 7 skips `retired` rows (D391, narrows D212). A row retired as unusable can have broken choices and must not refuse the bank.
- The refusal screen is a full-screen error list: the first 20 messages, then "and N more". Row N is the sheet row number, header = 1.
- When any case 5 fires, the screen leads with: "Some cells were converted on import. Import again with 'Convert text to numbers, dates, and formulas' unticked."
- Below the list sit the [import steps](#import-steps) and an "Open spreadsheet" link.
- An empty cell is not a case 5 failure. Case 5 is a number, a date or a boolean where text belongs.

Warn, as a dismissible amber banner on the home screen:

| Case | Text |
|---|---|
| a column the app does not know | "The bank has N unknown columns. The app ignores them." |
| orphan IDs | "N questions with study history are no longer in the bank. Their history is kept." |
| fewer `active` rows than `mock_question_count` | "The bank has N active questions. A Mock Test of M will be shorter." |

A dismissed banner stays away until the next page load.

Rules:

- The app checks no bank schema version. The header check stands in for it.
- **Changed answer.** When a question's `answer` differs from the `correct_answer` of its latest non-`skipped` `Attempts` row, the app treats it as due today in box 1. This is read-time only. Nothing is written until the next answer. Every other edit keeps the SR state.

## Import steps

Decisions: D209, D210, D313, D346. Ticket 21.

One procedure for the first import and every later one. The app holds this text as one constant. The menu dialog, the home panel and the refusal screen all show it. It matches `templates/import-steps.txt` in [0001, Step 10](0001-exam-bank-skill.md#step-10-export) word for word. This spec owns the wording, and a change here is copied there.

```
Import into the sheet:
1. Open the spreadsheet and select the Questions tab.
2. File > Import > Upload, pick export/<slug>-questions.csv.
3. Import location: "Replace current sheet". Never "Replace spreadsheet".
4. Separator type: Comma.
5. Untick "Convert text to numbers, dates, and formulas".
```

`<slug>` stays literal in the app, since an empty `Questions` tab gives no slug. The home panel and the refusal screen add an "Open spreadsheet" link and one line: "Then reload this page."

## Settings screen

Decisions: D156, D179, D213, D260, D314, D316 to D318. Ticket 27.

One screen, opened from the home header link. First open uses it in setup mode, with the title "Set up" and no Cancel. Fields, in order: exam name, exam date, question count, minutes, **Section** weights. `schema_version` is not shown.

"Save" validates every field and writes all five rows. The same checks run on every load, since the user can edit the tab by hand:

| Field | Rule |
|---|---|
| `exam_name` | non-empty, at most 100 characters |
| `exam_date` | a real `YYYY-MM-DD` date. A past date is allowed |
| `mock_question_count` | integer 1 to 200. A count above the active rows is allowed and gives a shorter test |
| `mock_minutes` | integer 1 to 600 |
| `section_weights` | empty, or comma-separated `n:w` |

`section_weights` rules:

- A question's **Section** number is the part of `subdomain` before the first dot.
- Each `n` is a **Section** number found on a row of `Questions`. No `n` appears twice.
- Every **Section** with `active` rows is present.
- Each `w` is a number of 0 or more, and at least one is above 0. Weight 0 leaves a **Section** out of every **Mock Test**.
- No sum rule. The sampler scales weights by their sum. The official PMLE weights sum to 101.
- "Save" strips a leading `section_weights:` and surrounding spaces before it checks and stores the value `[G16]`. `export` prints the line with that prefix, see [0001, Step 10](0001-exam-bank-skill.md#step-10-export), and the user pastes it whole. A hand edit in the tab must hold the bare pairs.

The field shows a hint: "Paste the `section_weights` line that `/exam-bank <exam> export` prints. Leave empty to follow the bank's own mix."

Effects of an edit:

- A running **Mock Test** is untouched by any edit.
- New count and minutes fill the next start panel.
- New weights apply from the next sample.
- A new exam date moves every capped due date at once.

A bad or missing value found on load opens this screen with the field marked and its rule shown. No study screen opens until "Save" passes.

## Home screen

Decisions: D152, D211, D215, D283, D312 to D315, D318, D320. Ticket 27.

One column, top to bottom. Card style follows the Review and Mock Test prototypes.

1. **Header.** `exam_name`, the exam date, the days-left text of [Dates and time](#dates-and-time), a "Settings" link.
2. **Warn banners** of the [bank check](#bank-check) and the load sequence.
3. **Mock Test card.** With no unfinished test: "Start Mock Test" and the line "50 questions · 120 min" from `Settings`. With one: "Resume test" and "k of N answered · H:MM:SS left · started `<date>`". "Start Mock Test" is hidden then.
4. **Review mode card.** The due count and "Start review". The due count is the Due filter count from `load()` (D392).
5. **Links.** "Mock Test history" and "Import bank".
6. **Bank line**, small, as a footer: "Bank: N active · N retired · N orphaned · updated `<date>`". The date is the newest `updated_at` in `Questions`, shown as a date. This line is how the user sees that an import landed.

Actions:

- "Start Mock Test" opens the [start panel](#start).
- "Resume test" opens the [pause screen](#pause-and-timer). The clock stays stopped until Resume there.
- "Start review" opens [Review mode](#review-mode) on the Due filter when the due count is above 0, else on All `[G8]`.
- "Import bank" opens an in-app panel with the [import steps](#import-steps). A web app page cannot open a Sheets menu dialog.

## Question card

Decisions: D12, D28, D32, D42, D193, D195, D197 to D200, D298, D305. Tickets 18, 23, 26. Prototype: `review-mode-prototype.html`, variant A.

One card design serves **Review mode**, the **Mock Test** and the results review. Each screen states what it turns off.

Layout, top to bottom: "Question N of M"; a pill row; the stem; the choices; the result banner; a 2x2 button grid; one wide primary button; any open inline panel below the grid.

- **Text.** Question, choice and explanation text is plain text. Line breaks show as written. Text between backticks shows in a monospace font. Everything else is escaped, never rendered as HTML.
- **Choices.** Radio buttons when `answer` has one letter, checkboxes when it has more, with the hint "Select N." Letters `A` to `F` label the choices in display order.
- **Choice order.** The results review shows stored order (D273). **Review mode** shows stored order too `[G9]`. The **Mock Test** shows the item's `choice_order`.
- **Pills.** The **Subdomain** pill reads "Subdomain 2.1: `<title>`". An **Uncertain answer** shows a warning pill "Uncertain answer" beside it, with the tooltip "This answer is disputed or was given with low confidence. Check it before you trust it." Further pills are named per screen.
- **Marking after grading.** Correct choices are green with a check. Wrong picks are red. A correct choice the user missed gets no extra state.
- **Explanations after grading.** One per choice, under its choice. Those of picked and correct choices start open. The rest start folded. Each toggles.
- **Buttons.** A button shows a filled state when its mark exists: a **Bookmark**, a non-empty note, an open **Report**.

### Bookmark

A toggle. It writes `QuestionState.bookmarked` at once.

### Note

Decisions: D146, D298.

Opens a side panel from the right over a dimmed screen. It is the same panel on all three screens.

- Title, an × close, a textarea with the placeholder "Mnemonics, traps to avoid…", the hint "Enter to save · Shift+Enter for new line", a counter "n/1,000 characters", "Clear note" and "Done".
- At most 1,000 characters.
- Every close saves: Done, Enter, ×, Esc, a click outside. "Clear note" empties the field, and the close then saves it empty.
- A save writes `note` and `note_updated_at`.

### Report

Decisions: D23, D161, D200, D226.

Opens an inline panel below the grid: a textarea with the placeholder "What looks wrong?", "Save report" and "Cancel".

- The note is required, 1 to 1,000 characters `[G10]`.
- With no open **Report** on the question, a save creates one: `status` `open`, `question_updated_at` from the bank row.
- With an open one, the panel loads its note and a save edits that row. The save also moves `reported_at` to now `[G10]`, so a re-check that ran on the old note does not resolve the new one.
- Under the textarea the panel shows the last resolved **Report** of this question, when one exists: "Last re-check, `<date>`: `<resolution>`".
- v1 has no way to withdraw a **Report** `[G10]`.

Inline panels open one at a time. Opening one closes the other.

## Review mode

Decisions: D8, D150, D162, D172, D173, D185, D193 to D201, D254, D389. Ticket 18.

Graded at once, one question at a time.

### Filter bar

At the top of the screen: All, Due, Wrong, Bookmarked, each with its count. Only `active` questions count.

| Filter | Holds | Order `[G8]` |
|---|---|---|
| All | every `active` question | unseen first in bank order, then seen by oldest `last_seen_at` |
| Due | seen and due, see [Dates and time](#dates-and-time) and the changed-answer rule | most overdue first |
| Wrong | `last_result` is `wrong` | newest `last_seen_at` first |
| Bookmarked | `bookmarked` is `TRUE` | bank order |

Due leaves unseen questions out `[G8]`. D190 defines due by `due_at`, and an unseen question has none.

A tie in any order above goes to bank order, the row order of `Questions`.

A filter pick calls `getReviewList(filter)`; the server builds the list (D389). The list is frozen when a filter is picked. An answered question stays in the list and keeps its place. Counts on the bar update live: the server sends the four counts with `load()`, `getReviewList`, `answerReview` and `setBookmark`, and the client never computes one (D392). Picking a filter again, the same one included, builds a new list.

An empty list shows "No questions match this filter."

### Answering

1. The user picks. "Submit answer" enables only when exactly N choices are picked, N being the number of letters in `answer`.
2. Submit grades on the server, see [Grading and spaced repetition](#grading-and-spaced-repetition). One submit appends one `Attempts` row.
3. The card locks. The banner reads "Correct!" or "Incorrect", followed by the correct letters. Marking and explanations show as in [Question card](#question-card).
4. The only way on is "Next question". On the last question it reads "Finish", and leads to an end card: "End of this list. N answered, N correct." with "Pick a filter" and "Home" `[G8]`.

There is no way past a question without answering it, as in the prototype. The user leaves a list by picking a filter or going home.

Pills: **Subdomain**, **Uncertain answer**, and an SR pill reading "Unseen" or "Box N · due `<date>`". The pill shows the effective box and due date the server sent, never the stored `due_at`.

Buttons, 2x2: **Bookmark**, Note, **Report**, Copy prompt. Copy prompt is disabled until the question is graded.

**Review mode** stays open while a **Mock Test** is unfinished.

## Grading and spaced repetition

Decisions: D8, D9, D150, D153, D158, D165, D172 to D174, D186, D190, D206, D292, D318. ADR 0003. Tickets 08, 17.

### Grading

All or nothing. A question is `correct` when the picked letters equal `answer` as a set. Anything else with at least one pick is `wrong`. No pick is `skipped`, which only a **Mock Test** can produce.

The server grades. The client never sends a result.

### Leitner

Five boxes. Intervals in days for boxes 1 to 5: 1, 2, 4, 8, 16. The intervals are a design choice with no primary source.

On a graded answer, with "today" as the grading date:

| Result | Condition | `box` | `due_at` |
|---|---|---|---|
| `correct` | unseen, or due | one up, at most 5 | today + the new box's interval |
| `correct` | seen and not due | unchanged | unchanged |
| `wrong` | any | 1 | today + 1 |
| `skipped` | any | no change to the row at all | |

- "Due" here uses the capped due date and the changed-answer rule of the [bank check](#bank-check). Under that rule the starting box is 1, so a correct answer gives box 2.
- `correct` and `wrong` also add 1 to `attempts`, add 1 to `correct_count` on `correct`, and set `last_seen_at` and `last_result`.
- The same rule serves both modes. A **Mock Test** applies it at submit, with the submit time as `answered_at`.
- A correct answer on a question that is not due leaves the box alone, so repeats in **Review mode** cannot inflate it.
- There is no interval compression and no final-week mode. The cap already makes everything due before the exam.

### Rebuild

`[G7]` `Attempts` is the source of truth, and the SR fields are a cache. The rebuild replays every `Attempts` row in sheet order through the Leitner table, taking each row's date from `answered_at` in the spreadsheet's time zone and using the uncapped `due_at` for "due". It applies the changed-answer rule inside the log: a row whose `correct_answer` differs from that of the question's previous non-`skipped` row starts from box 1 and due. It then rewrites `box`, `due_at`, `attempts`, `correct_count`, `last_seen_at` and `last_result` on every `QuestionState` row, adding rows as needed. `bookmarked`, `note` and `note_updated_at` stay as they are.

It runs from the menu item, and when the load sequence recreates `QuestionState`. A later move to another algorithm replays the same log.

## Copy prompt

Decisions: D201, D202, D254 to D264, D276, D310, D390. Ticket 24.

Copy prompt builds a prompt about the current question for the user to paste into a chat LLM. It is offered after grading in **Review mode** and on each question of the results review. A **Mock Test** has no Copy prompt, since the prompt holds the correct answer.

The button opens an inline panel: a level picker, a preview of the full prompt, and "Copy". The level is Beginner, Intermediate or Expert, default Intermediate. A picked level stays for the page session.

The template is a constant in the app code. No setting edits it. Plain text only.

```
I am studying for the {exam_name} exam. Explain this practice question.

Level: {level}. {level sentence}

Subdomain {number}: {title}

Question:
{stem}

Choices:
A) {choice}
B) {choice}

Stated correct answer: {letters}
My answer: {letters} ({correct|wrong})
Sources disagree on this answer. Check it first.

Explanations I already read:
A) {explanation}
B) {explanation}

Do this:
1. Do not repeat the explanations above. Go deeper.
2. For each choice, say why it is right or wrong in this scenario.
3. Name the one fact that decides the question.
4. If you think the stated answer is wrong, say so and give your reason.
5. For each key fact, give the cloud.google.com page title. Give a URL only when you are sure the page exists.
6. End with one rule of thumb I can reuse on similar questions.
```

Rules:

- `{exam_name}` comes from `Settings`.
- The "Sources disagree" line appears only on an **Uncertain answer**.
- Every filled choice and its explanation is listed. The user's note is left out.
- Letters follow the order shown on screen. Both screens that offer Copy prompt show stored order, so these are the stored letters.
- On a `skipped` question of the results review the line reads `My answer: none (skipped)` (D390, amends D276).
- On a question edited since its test, Copy prompt is disabled with the tooltip "Disabled: the question changed since this test, so the stored answer may not match these choices."

Level sentences. A level changes depth only, never the task list:

- Beginner: "I am new to Google Cloud ML. Define each service you mention in one sentence and use plain words."
- Intermediate: "I know the core Google Cloud ML services. Skip definitions. Focus on why each choice fits or fails."
- Expert: "Be brief. Focus on edge cases, trade-offs and limits that decide between the close choices."

### Copying

The sandboxed iframe has no documented `clipboard-write` permission, so "Copy" runs a fallback chain, all inside the click handler:

1. `navigator.clipboard.writeText`.
2. On rejection, a textarea with `select()` and `document.execCommand('copy')`, checking the return value.
3. On failure, the panel shows the prompt in a read-only textarea, already selected, with "Press Ctrl+C to copy."

A success shows "Copied." Which step runs on a real deployment is a [Confirm at build](#confirm-at-build) item. Observed 2026-11-18 in the deployed web app on Chromium 156: step 1 is rejected with `NotAllowedError` (write permission denied) and step 2 succeeds, so step 2 is the path that runs. Step 3 and its Ctrl+C line stay as the fallback until Firefox is checked.

## Mock Test

Decisions: D9, D17, D151, D152, D160, D166 to D171, D175 to D192, D287 to D298, D314, D315, D388. Tickets 17, 23. Prototype: `mock-test-prototype.html`, variant D.

A timed test, graded only at submit. At most one test is unfinished at a time.

### Start

"Start Mock Test" opens a start panel with question count and minutes, filled from `Settings`.

- Ranges are those of the [Settings screen](#settings-screen): 1 to 200 and 1 to 600.
- A count change sets minutes to count × `mock_minutes` ÷ `mock_question_count`, rounded up, until the user edits minutes by hand.
- The values apply to this test only. `Settings` is unchanged. `score_pct` still compares across tests.
- "Start" runs the sampler, appends the `MockTests` row with `status` `in_progress`, `question_count` = the number sampled, `minutes_allowed` and `seconds_left` = minutes × 60, and writes the `MockTestItems` rows.
- Question order and each question's choice order are shuffled once, here.
- When the sampler returns fewer questions than asked, the test shows the notice "This test has N questions, not M: the bank has only N active questions."

### Sampler

Only `active` questions with a row in `Questions` are candidates. All state is read as of the start time.

**1. Section split.** Split the question count across **Sections** by weight.

- Weights come from `section_weights`. When it is empty, a **Section**'s weight is its count of `active` questions.
- Share = count × weight ÷ sum of weights. Round by largest remainder. A tie goes to the higher weight, then the lower **Section** number `[G11]`.
- A **Section** with fewer candidates than its share takes all it has. Its shortfall goes to the other **Sections** with candidates left, by weight, with the same rounding. Repeat until nothing is left to place or no **Section** has candidates.
- A bank smaller than the count gives a shorter test.

**2. Buckets.** Inside each **Section** share: 40% due, 30% unseen, 30% weak-fill. Round by largest remainder, ties to due, then weak-fill, then unseen.

| Bucket | Pool | Pick order inside a **Subdomain** |
|---|---|---|
| due | seen and due | most overdue first |
| unseen | no `QuestionState` row, or `box` 0 | random |
| weak-fill | seen and not due | lowest box, then oldest `last_seen_at` |

A tie in a pick order goes to bank order.

**3. Drawing.** For each slot of a bucket, draw one **Subdomain** of the **Section** at random among those with candidates left in that bucket's pool, weighted by weakness with a floor of 0.1. Take that **Subdomain**'s first question in the bucket's pick order.

**4. Spill.** A bucket whose pool runs out passes its open slots on in this order: due, weak-fill, unseen. Slots still open after that are filled from any candidate left in the **Section**, oldest `last_seen_at` first, ties in bank order `[G11]`.

**5. Shuffle** the final list, and the choices of each question.

**Subdomain weakness** = `1 - (correct + 2) / (attempts + 4)` over the **Subdomain**'s last 30 non-`skipped` `Attempts` rows, both modes, missing and `retired` IDs left out. A **Subdomain** with no attempts scores 0.5.

### Screen

One column.

- **Question card**, with the timer bar at the top inside it: "Time left", `H:MM:SS`, and "Pause". The timer turns red under 5 minutes.
- **Navigator card** below it: the grid, a legend, the counts line "N answered · N unanswered · N Flagged", and "Submit test".

The card is the [Question card](#question-card) without grading. It has no banner, no marking, no explanations, no "Submit answer" and no Copy prompt.

- A pick saves at once. There is nothing to confirm per question.
- Multi-select picks are capped at N. A further pick shows "Unpick one first". The hint reads "Select N. k of N picked." with a "Clear" link.
- "Previous" and "Next" replace the primary button. The last question shows "Review & submit", which opens the submit confirm.
- Buttons, 2x2: **Flag**, **Bookmark**, Note, **Report**. **Flag** takes the Copy prompt slot. Note and **Report** write to `QuestionState` and `Reports`, not to the test. They stay even though an old note or an open **Report** can hint at the answer.
- Pills: the **Subdomain** pill only. The **Uncertain answer** and SR pills are hidden until submit. A **Flagged** question shows "Flagged". A reset item shows "Edited in re-import: answer cleared".
- The Note side panel does not stop the clock. Pause and any submit save an open note first.

Navigator cell, one per question, showing its number:

| Look | Means |
|---|---|
| filled | answered |
| half-filled | part answered: a multi-select with fewer than N picks |
| empty | unanswered |
| ⚑ corner | **Flagged** |
| dashed amber border | reset by a re-import |
| outline | current question |

Answered and **Flagged** are independent. A click jumps to that question. Until submit the user can open any question, change any answer and toggle any **Flag**.

Notices are amber, dismissible, and sit above the question card and on the pause screen.

### Saving

Decisions: D168. `[G12]` covers the failure handling.

- Every answer change and every **Flag** change saves the changed items to `MockTestItems`, and `seconds_left` to the `MockTests` row, in one server call. There is no heartbeat.
- The server never raises `seconds_left` above the stored value.
- The client keeps the changes of a failed call and sends them with the next one. After three failed calls in a row it shows a red banner "Not saved. Check your connection." until a call succeeds.
- Pause and submit send any unsaved changes in their own call. Pause calls `saveMockTest` (D393).
- A save for a test that is no longer unfinished is rejected. The client shows "This test was already submitted or discarded in another tab." and returns home.

### Pause and timer

- The client counts down from `seconds_left`. The clock runs only while the test screen or the submit confirm is open.
- **Pause** saves `seconds_left` and replaces the whole screen. It changes no `status` (D388). The pause screen shows the time left, the answered and **Flagged** counts, any notices, and "Resume". Question, choices and navigator are hidden. There is no limit on pauses.
- **Resume** starts the clock and returns to the question the user left. It makes no server call.
- An unfinished test always opens on the pause screen. After an unclean close the clock stands at the last saved `seconds_left`, so a crash loses only the clock time since the last save.
- **Discard** sits on the pause screen only, as a "Discard test…" link under Resume, followed by a confirm. It sets `status` `discarded`, clears `MockTestItems` at once and writes no `Attempts`.
- **At zero** the test submits itself with no confirm. It first closes any open panel or modal, saving an open note.

### Submit confirm

"Submit test" opens a modal. The clock keeps running behind it.

- The unanswered count, with the part-answered count named inside it, and the **Flagged** count.
- Each count comes with jump buttons by question number. A jump closes the modal and opens that question.
- "Back to test" and "Submit test".

### Submit

Decisions: D158, D170, D180, D184, D186, D273, D292, D304. ADR 0003.

Under the script lock, in this order:

1. Append one `Attempts` row per item, in `position` order: `answered_at` = the submit time, `mode` `mock`, the `test_id`, `selected`, `correct_answer` and `question_updated_at` from the bank row, `flagged` from the item, and `result`.
2. Update `QuestionState` per the [Leitner table](#leitner).
3. Set the `MockTests` row: `status` `submitted`, `submitted_at`, `seconds_left`, `correct_count`, `score_pct`.
4. Clear `MockTestItems`.

Result per item:

| Picks | `result` | SR update |
|---|---|---|
| equal to `answer` | `correct` | yes |
| at least one, not equal, part-answered included | `wrong` | yes |
| none | `skipped` | no |

Score: `correct_count` = the `correct` rows. `score_pct` = `correct_count` ÷ `question_count` × 100, one decimal. `skipped` counts as wrong. There is no pass mark. Time used = `minutes_allowed` × 60 − `seconds_left`.

Before step 1 the server runs the [re-import reconcile](#re-import-during-a-test). It writes the sent `changes` first, then reconciles, so a change never lands on a shifted position. When it drops or resets an item on a manual submit, the server submits nothing and returns the test, shown on the pause screen with the notice. At zero seconds it submits anyway, and a reset item is `skipped` `[G13]`.

Recovery: on load, a test that has `Attempts` rows and is not `submitted` finishes from step 2 and appends nothing. Step 2 skips a question whose `last_seen_at` already equals the test's `answered_at`, so a second run changes nothing `[G13]`.

After submit the app opens the [results screen](#results-screen).

### Re-import during a test

Decisions: D183, D290, D296.

A re-import is allowed while a test is unfinished. The reconcile runs when the unfinished test is loaded and before a submit:

- An item whose question is missing or `retired` is dropped. `question_count` goes down by one. Positions close up.
- An item whose bank `updated_at` differs from its `question_updated_at` keeps its place and its **Flag**, loses its answer, gets a new shuffled `choice_order` and the new `question_updated_at`.
- A notice gives the counts: "The bank changed during this test. N questions were removed, the test now has M. K questions were edited and their answers cleared:" followed by a link to each reset question.
- When every item is dropped, the test is discarded and the home screen says so.

The "Edited in re-import" pill and the dashed navigator border last for the page session `[G13]`. No column stores them.

## Results screen

Decisions: D162, D184, D269 to D278, D281 to D284, D299 to D306, D308, D310, D389. Tickets 25, 26. Prototype: `results-history-prototype.html`, variant A.

Opened after a submit and from a history row or chart point. The app rebuilds any past test from its `MockTests` row and its `Attempts` rows by `test_id`. No tab stores a results view.

Top to bottom:

1. Links: "Home" and "← Mock Test history".
2. Right after a submit, a blue line: "Test submitted." or "Time ran out. The test submitted itself; unanswered questions count as skipped." Each links to the history.
3. **Header card.** The date, a "timed out" pill when `seconds_left` is 0, the score percent, correct / question count, the skipped count, time used of time allowed. No pass or fail.
4. **"Score by Section" card.**
5. **Review card.** The filter bar, the result grid, a legend.
6. **One question card** with "Previous" and "Next".

### Score by Section

- The server builds the breakdown and returns it with `getResults` (D389).
- One row per **Section**: its label, correct / count, percent. A click expands the row to its **Subdomains**, each with number, title, correct / count and percent.
- A **Section** row is labelled "Section N". It has no title, since the sheet carries **Subdomain** titles only `[G14]`.
- Each question is grouped by its current **Subdomain** in `Questions`. A re-tag can shift an old breakdown, never the total.
- An italic "Not in bank" row holds the questions whose ID is missing, when there are any. Tooltip: "Questions removed from the bank since this test. Still in the score."
- A "Total" row equals the header.
- Footnote: "Skipped counts as wrong. Grouped by each question's Subdomain today."

### Review

Read-only. Opening a question writes no `Attempts` row and changes no SR state.

- Questions show in test order, choices in stored order.
- **Filter.** A result filter, All, Correct, Wrong or Skipped, combined with a "⚑ Flagged" toggle. The result buttons are disjoint, so Wrong leaves skipped out. Their counts follow the toggle. The **Flagged** count is the test's total. Tooltip on the toggle: "Only questions you Flagged during the test. Combines with the result filter."
- "Previous" and "Next" walk the filtered list. An empty combination shows a line such as "No Flagged wrong questions in this test." with "Show all".

Result grid, one cell per question, numbered in test order under any filter:

| Look | Means |
|---|---|
| green | correct |
| red | wrong |
| dashed grey | skipped |
| ⚑ corner | **Flagged** |
| ✎ | edited since this test |
| ∅ | not in the bank |
| outline | current |

Cells outside the filter are dimmed and cannot be clicked.

Question card: the [Question card](#question-card), graded and read-only.

- Banner: "✓ Correct!", or "✕ Incorrect" with the correct letters and "You picked …", or a grey "– Skipped" with "Not answered. Correct answer: …". The result also shows at the top right of the card.
- Choices cannot be clicked. Correct choices are green, labelled "✓ correct" or "✓ your pick". Wrong picks are red.
- Explanations open as on any graded card.
- Pills: **Subdomain**, **Uncertain answer**, "⚑ Flagged" when it was, "retired" when the question is. No SR pill, since that is today's state and not the test's.
- Buttons, 2x2: **Bookmark**, Note, **Report**, Copy prompt. There is no **Flag** button.

Questions that changed since the test:

| Case | Shows |
|---|---|
| edited: `updated_at` differs from the attempt's `question_updated_at` | current text and answer, the stored result, an amber notice "Edited since this test…", a banner without letters reading "Recorded at the test.", no picked marks, only the correct choices' explanations open, Copy prompt disabled |
| `retired` | as normal, with the "retired" pill |
| ID missing | one dashed line: question number, ID, "no longer in the bank", the result, the **Flag** if any. No buttons. It keeps its grid position and counts in the score |

An edit can reorder choices, so stored letters on an edited question may be stale. That is why its picks are hidden.

## History screen

Decisions: D271, D272, D279, D280, D285, D307. Tickets 25, 26.

Top to bottom: a "Home" link, the title "Mock Test history", a "Score over time" chart card, a table card.

- Only `submitted` tests are listed, newest first. A discarded test has no score.
- **Table.** Date, Score, Correct as correct / question count, Time used, and a "⏱ timed out" pill when `seconds_left` is 0. Every value comes from the `MockTests` row. A row click opens that test's results.
- **Chart.** Inline SVG with no chart library. A 0 to 100% grid. Points evenly spaced in test order, the date under each and the percent above it. A hollow amber point marks a timed-out test. No pass line. A point click opens that test, and hovering a point highlights its table row. One test shows one point and no line.
- Empty state: a card reading "No Mock Tests yet." with a "Home" link.
- v1 cannot delete a past test.

## Report loop

Decisions: D23, D161, D216, D219, D225, D226. Ticket 22.

The app writes **Reports** and resolves them. The skill re-checks them. The app never reaches the skill and the skill never reaches the sheet, so the loop runs through two files:

1. The user saves a **Report** in the app, see [Report](#report).
2. The user downloads the `Reports` tab as CSV and runs `/exam-bank <exam> recheck`, then `export`. That half is [0001, Recheck route](0001-exam-bank-skill.md#recheck-route).
3. The user imports the new bank.
4. On the next load the app resolves.

Resolve rule, step 7 of the [load sequence](#load-sequence): for each `open` row whose question is in `Questions` with a `rechecked_at` later than the row's `reported_at`, set `status` `resolved`, `resolved_at` to now, and copy the bank row's `recheck_note` into `resolution`.

- Only `rechecked_at` resolves a **Report**. It stays `open` when its question changed for another reason, and when its ID is missing.
- After a resolve, reporting the same question again creates a new row.
- The home screen then shows one dismissible line: "N Reports were re-checked. Open a question's Report panel to read the result." `[G10]`
- An overturned answer also makes the question due in box 1, by the changed-answer rule of the [bank check](#bank-check).

## Server interface

Decisions: D168, D180, D203, D388, D389, D392, D393. ADR 0003. The seam was confirmed by the user on 2026-11-17. The function list is `[G15]`, confirmed the same day.

The client calls the server only through the functions below, over `google.script.run`. This list is the app's one test seam. Arguments and returns are JSON-like. Every function that writes takes the script lock, waits up to 10 seconds for it, and returns an error the client shows as "The sheet is busy. Try again." when it cannot get it.

| Function | Does | Returns |
|---|---|---|
| `load()` | the [load sequence](#load-sequence) | `{screen, ...}`. `screen` is `wipe`, `version`, `refused`, `settings` or `home`. `home` carries the active and `retired` bank rows, `QuestionState` with each seen row's effective box and due date added, the cap and the changed-answer rule applied, the question IDs with an open **Report**, settings, warnings, the four **Review mode** filter counts (All, Due, Wrong, Bookmarked; D392), the unfinished test summary, and today's date |
| `saveSettings(values)` | validates and writes the five rows | field errors, or the new `load()` result |
| `answerReview(questionId, selected)` | grades, appends the `Attempts` row, updates `QuestionState` | `result`, the correct letters, the new state row in the same form, the four filter counts |
| `setBookmark(questionId, on)` | writes `bookmarked` | the state row, the four filter counts |
| `saveNote(questionId, text)` | writes `note` and `note_updated_at` | the state row |
| `saveReport(questionId, note)` | creates or edits the open **Report** | the row |
| `getReports(questionId)` | reads | the open row and the last resolved row |
| `startMockTest(count, minutes)` | samples, writes the test and its items | the test, with any notice, or an error when a test is already `in_progress` |
| `getMockTest()` | reconciles, then reads the unfinished test | the test, for the pause screen, with any notice and the current bank rows of its reset items, or `discarded` when the reconcile dropped every item |
| `saveMockTest(changes, secondsLeft)` | writes changed items and the clock; Pause calls it too (D393) | ok, or `not_unfinished` when no test is `in_progress` |
| `discardMockTest()` | sets `discarded`, clears the items | ok |
| `submitMockTest(changes, secondsLeft, timedOut)` | the [submit](#submit) | the `test_id` and the changed `QuestionState` rows, or the unfinished test, for the pause screen, with a notice and the current bank rows of its reset items, or `discarded` when the reconcile dropped every item |
| `getResults(testId)` | reads, builds the [Score by Section](#score-by-section) breakdown | the `MockTests` row, its `Attempts` rows, and the breakdown: **Section** rows each with its **Subdomain** rows, the "Not in bank" row when one exists, and the Total row; every row holds correct, count and percent (D389) |
| `getReviewList(filter)` | builds one [Review mode](#filter-bar) list | the question IDs of that filter, in its order (D389), and the four filter counts (D392) |
| `getHistory()` | reads | the `submitted` `MockTests` rows |
| `rebuildState()` | the [rebuild](#rebuild), menu only | the row count |

A `changes` entry is `{position, selected, flagged}` with `selected` in stored letters. The client maps display letters to stored letters through `choice_order` before it sends.

The client holds the bank, answers included. That is fine for one user studying alone, and it lets the results review and Copy prompt work without a call per question.

### Adapter

Server code touches Apps Script services through one adapter object and nowhere else:

- Tabs: read a tab as rows keyed by header, append rows, rewrite rows, clear a tab below its header, create a tab with headers.
- Script properties: get and set.
- Lock: take and release.
- Clock: now as a UTC timestamp, today in the spreadsheet's time zone, and the date of a given UTC timestamp in that time zone.
- Random: one function returning a number in [0, 1).
- URLs: the spreadsheet URL and the web app URL.

The Apps Script build of the adapter wraps `SpreadsheetApp`, `PropertiesService`, `LockService` and `ScriptApp`. The test build is an in-memory fake with a settable clock and a seeded random.

## Testing

Decisions: D376.

Tests run in Node with `node --test`, which needs no dependency. Node 22 is already a prerequisite for clasp. They call the server functions of [Server interface](#server-interface) against the fake adapter and check two things only: what the function returns, and the rows left in the fake tabs. A good test here never calls an internal helper, never checks call order on the adapter, and would still pass after a rewrite of the server internals.

The repo has no earlier tests to follow. 0001's scripts are not built yet.

Each test builds its sheet from small fixtures: a bank of a dozen rows across three **Sections**, a clock, a seed.

What the tests cover, by area:

- **Load sequence.** First open creates seven tabs and sets the mark. Mark present and `Attempts` missing returns `wipe` and creates nothing. A copied sheet sets the mark. A recreated `QuestionState` is rebuilt.
- **Bank check.** One test per refuse case and per warn case. A number in `subdomain` refuses with the "Convert text" lead line. Headers in another order pass. An extra column warns.
- **Settings.** Each field rule, the `section_weights` rules, weights summing to 101, a hand-edited bad value returning `settings` on load.
- **Grading.** Single and multi-select, exact set match, one `Attempts` row per answer with every column.
- **Leitner.** Each row of the table. A correct answer on a not-due question holds the box. The exam-date cap makes a question due without a rewrite. The cap is off after the exam date. A changed `answer` makes the question due in box 1. A `skipped` row with the new answer does not clear that.
- **Filters.** Counts and order of the four **Review mode** lists, with `retired` and missing IDs left out.
- **Sampler.** With a fixed seed: the **Section** split and its rounding, weight 0, empty weights, a short **Section**, a short bank, the 40/30/30 split and each spill step, the pick order per bucket, no `retired` or missing ID, no question twice.
- **Mock Test run.** Start writes the rows. A save writes only the changed items and never raises the clock. Pause, discard. One unfinished test at most. A second start is refused. A save after submit returns `not_unfinished`.
- **Submit.** Rows in `position` order, `skipped` and part-answered results, the score, `flagged` copied, `MockTestItems` cleared. A submit cut off after step 1 finishes on the next `load` and appends nothing. Running that recovery twice changes nothing.
- **Re-import during a test.** Dropped, reset and all-dropped cases, on load and on submit, and the zero-seconds submit.
- **Results and history.** A test rebuilt from `Attempts`, the breakdown adding up to the stored score with a "Not in bank" row, an edited question, only `submitted` tests in the history.
- **Reports.** Create, edit moving `reported_at`, one open row per question, resolve on `rechecked_at`, no resolve for a missing ID, a new row after a resolve.
- **Rebuild.** A replay gives the same SR fields the live path gave, on fixtures where the exam-date cap never applied, a changed answer included. It keeps bookmarks and notes.
- **Copy prompt.** The prompt builder is client code with no server call. It is one pure function, alone in a client `.html` file that holds a single script tag. The test strips the tag, evaluates the body and calls the function. It is tested for each level, the **Uncertain answer** line, a `skipped` answer and a six-choice question. This is the one test outside the seam.

Not tested by code: screen layout, the clipboard chain, the Sheets import dialog, clasp and deployment. Those are the manual checks in [Confirm at build](#confirm-at-build), plus one pass through each screen on a real deployment against the three prototypes.

## README parts

Decisions: D18, D322 to D325, D330 to D333, D336, D338 to D340. Ticket 28.

The last build task assembles the root `README.md`. This spec owns the app visuals in the Showcase, the Try it path, section 4, Part 2, and the app side of sections 5 and 6 (RV-D22). The rest, the visual rules and the rules that bind every part, are in [0001, README parts](0001-exam-bank-skill.md#readme-parts). RV-Dn cites the [readme-visuals interview log](../../.scratch/readme-visuals/interview-log.md).

### Demo bank

`docs/demo/demo-bank.csv`, a **Demo bank** in the [CSV contract](0001-exam-bank-skill.md#csv-contract) (RV-D2, RV-D9, RV-D25):

- 25 original PMLE-style questions, written for this repo. None is scraped, given or reworded from a source.
- The **Sections** and **Subdomains** of `templates/exams/pmle.example.yaml`, with at least 5 **Subdomains** covered.
- **Lineage** `created`, a real explanation per choice, and 1 or 2 **Uncertain answers**.
- It passes the [Bank check](#bank-check) when imported with the [import steps](#import-steps). `app/tests/demo-bank.test.js` checks this.
- `scripts/build_demo_bank.py` writes the file. Edit the questions there, never the CSV by hand.
- The user reviews it. After any edit, rerun the capture tool.

### Visuals, app side

Made by two committed dev tools under `scripts/`, covered by the checks in `docs/checks.md` (RV-D7, RV-D8):

- A preview server in Node. It serves `client/index.html` with the `include_` scriptlets inlined and a stub `google.script.run` that posts each call to the server. The server runs `makeServer` from `tests/load-server.js` over one fake adapter from `tests/fake-adapter.js` that lives for the whole session, seeded with the Demo bank and valid Settings. The clock starts at a fixed time and then follows real time. With `PREVIEW_CLOCK_CONTROL=1` it adds `POST /dev/advance?days=N`, which only the capture tool uses, to spread Mock Tests over days for the history chart. `app/tests/preview.test.js` is its smoke test.
- A Playwright capture script. It drives the preview, records each clip, and converts it to GIF with ffmpeg within the [visual rules](0001-exam-bank-skill.md#visual-rules). It stops when a GIF breaks the size or length budget.

Showcase images (RV-D6, RV-D18):

- Hero GIF: **Review mode**. Pick an answer, see it graded, read the per-choice explanations. Under 15 s.
- Four feature tiles: **Review mode** with explanations (the hero, smaller); a **Mock Test** GIF with the timer, a **Flag** and submit; results by **Section**; History and the **Report** loop.

Part 2 images (RV-D11, RV-D29), masked per the visual rules:

- `docs/assets/unverified-app.png`, the "Google hasn't verified this app" screen, beside step 2. The agent makes a throwaway sheet with `clasp create-script`, opens it in Chrome, and triggers authorization. The screen opens in a separate popup window, so the agent takes a desktop screenshot with no other window over the popup, then crops and masks it. The user approves tool access and clicks Advanced and Allow. The agent moves the throwaway sheet to Trash when done (RV-D30).
- `docs/assets/deploy-dialog.png`, the New deployment dialog, beside step 3.

### Try it in 5 minutes

Showcase item 7 (RV-D16, RV-D25). Run Part 2 steps 1 to 4, then step 5 with `docs/demo/demo-bank.csv` in place of the exported CSV. In step 6, use exam name "PMLE (demo)" and the `section_weights` line for the Demo bank, printed in full in the README. Then practice. No Opus run is needed. The build checks this path once on the throwaway sheet from the Part 2 images, before that sheet goes to Trash (RV-D30).

### 4 Part 2: Deploy the study app

One path: clasp. There is no editor copy-paste path and no public template sheet.

Step 1, create the sheet and push the code:

```bash
cd app
clasp login
clasp create-script --type sheets --title "PMLE study"
git checkout -- appsscript.json
clasp push --force
```

Two lines under it: `clasp create-script` makes a new Google Sheet with the script bound to it, prints both URLs, and overwrites `appsscript.json` with a default manifest, so `git checkout -- appsscript.json` restores the repo's. Plain `clasp push` prints "Skipping push." in a non-interactive shell because the remote manifest differs, so use `--force`. Result 2026-11-18 (clasp 3.4.1).

Step 2, authorize. Open the new sheet and reload it, so the "Study app" menu appears. Click "Study app" > "Open study app". Google shows a dialog "Authorization required: A script attached to this document needs your permission to run." Click OK; a Google popup opens (already signed in, so there is no account chooser). It shows "Google hasn't verified this app". Click the red-box link "Go to `<sheet name>` (unsafe)"; there is no "Advanced" link. The next screen, "`<sheet name>` wants access to your Google Account", lists two permissions with unticked boxes: "View and manage spreadsheets that this application has been installed in." and "Display and run third-party web content in prompts and sidebars inside Google applications." Tick "Select all" (or both boxes), scroll down, click "Continue". The popup closes with no further dialog; click "Open study app" again. This warning is expected for a script you own and run yourself. Result 2026-11-18: observed on a fresh unauthorized sheet; clicking "Open study app" again then ran the script (on an undeployed sheet it showed the dialog "Study app" with the old text "Deploy the web app first", now "Open the web app once from its URL first. See the README, Part 2, step 4."); the Deploy dialog's "Authorize access" button opens the same popup.

Step 3, deploy. In the sheet open Extensions > Apps Script. Click Deploy > New deployment. The type "Web app" is already selected, "Execute as" reads "Me (`<your email>`)" and "Who has access" reads "Only myself", all filled in from the manifest. Click Deploy. If step 2 was skipped, the dialog first says "The Web App requires you to authorize access to your data." with an "Authorize access" button, which opens the same Google screens. The dialog then shows the Deployment ID and the web app URL ending in `/exec`. Result 2026-11-18.

Step 4, first open. Open the web app URL the Deploy dialog showed. The app creates its tabs and shows the import steps. From now on "Study app" > "Open study app" in the sheet links to the same URL. Before this first open that menu item cannot know the URL, and its dialog says so.

Step 5, import the bank. The [import steps](#import-steps) word for word, with the PMLE path `exam-bank/pmle/export/pmle-questions.csv`. This is the README's only copy. Then: reload the app.

Step 6, Settings. Enter the exam name and exam date. Paste the `section_weights` line that `export` printed. Save.

One closing line: study data lives in the sheet's other tabs. Never import with "Replace spreadsheet".

Links: [Bank check](#bank-check) for a refused bank, [Settings screen](#settings-screen) for the field rules.

### 5 Upkeep, app side

- **Re-import.** After any new export, repeat step 5. Study history is kept, see [Sheet tabs](#sheet-tabs).
- **Update the app code.** `git pull`, then:

  ```bash
  cd app
  clasp push --force
  clasp list-deployments
  clasp update-deployment <deploymentId>
  ```

  One line: pushed code reaches the app only after `update-deployment`. `list-deployments` prints one `<deploymentId> @<version>` line per deployment plus an `@HEAD` line; `<deploymentId>` is the one with a version number, and `update-deployment` moves it to a new version under the same ID, so the web app URL does not change. Result 2026-11-18.
- **Move to another Google account.** In the sheet, File > Make a copy. The script and the study history come along. Then repeat steps 2 to 4 in the copy.
- **Add another exam, app half.** One clasp settings file per exam, `app/.clasp-<slug>.json`, and `--project <absolute path>` on every clasp command. `create-script --project` fails with "File or directory does not exist" until the file exists, so create it with `{}` first. A relative path such as `.clasp-pde.json` creates the sheet but breaks every later command with "srcDir escapes project root" (clasp 3.4.1), so use the absolute path:

  ```powershell
  cd app
  '{}' | Set-Content .clasp-pde.json
  $p = (Resolve-Path .clasp-pde.json).Path
  clasp --project $p create-script --type sheets --title "PDE study"
  git checkout -- appsscript.json
  clasp --project $p push --force
  ```

  Tested in PowerShell on Windows only. A Git Bash path such as `$PWD/.clasp-pde.json` still failed with "srcDir escapes project root". Then steps 2 to 6 in the new sheet. One code folder serves every exam sheet. Result 2026-11-18: the named file was written and `.clasp.json` was left alone.

### 6 Troubleshooting, app side

One line each, message then fix, with a link to the named section:

- The app says a column "is not text": import again with "Convert text to numbers, dates, and formulas" unticked. [Bank check](#bank-check).
- The app says its tabs are gone: in the sheet, File > Version history, restore the version from before the import. [Load sequence](#load-sequence).
- "Google hasn't verified this app": expected for your own script. Advanced > Go to … (unsafe). Part 2, step 2.
- Copy prompt shows a text box instead of copying: press Ctrl+C. [Copying](#copying).
- The Settings screen opens on load: fix the marked field and save. [Settings screen](#settings-screen).
- A code change does not show in the app: run `clasp update-deployment`. Upkeep.

## Confirm at build

Decisions: D202, D214, D339. Ticket 06 [U] marks, ticket 21, ticket 28.

A result here changes text or a small mechanism, never a decision. The README is written after these, with no placeholder and no untested click path. Items 1 to 4, 10 and 12 run first, on a throwaway deployment before the app is built, since each can change a mechanism. D202 makes the clipboard check a build prerequisite.

1. **Clipboard.** Which step of the [copy chain](#copying) works in the deployed web app, in Chrome and Firefox. Decides whether the Ctrl+C troubleshooting line stays. Result 2026-11-18: Chromium done, Firefox pending (user step). See [Copying](#copying).
2. **"Replace current sheet" keeps the tab name** `Questions`. If it renames the tab, the import steps gain a rename line, here and in 0001's `import-steps.txt`.
3. **The "Convert text" checkbox**: its exact wording and its default. Line 5 of the import steps follows it, in both specs.
4. **The "set up" mark survives "Replace spreadsheet".** If a script property does not, pick another store that does.
5. **The unverified-app screen**: the exact click path and wording for README step 2. Result 2026-11-18: the menu item opens "Authorization required" with Cancel and OK, and OK opens a Google popup that only the user can drive. Popup path: "Google hasn't verified this app" > link "Go to `<sheet name>` (unsafe)" (no Advanced link, no account chooser) > "`<sheet name>` wants access to your Google Account" with two unticked permission boxes and a "Select all" box > Continue (there is no Allow button); the popup then closes by itself. See README step 2.
6. **The web app access level**: the exact label for "Only myself" in the deploy dialog. Result 2026-11-18: the dialog "New deployment" has type "Web app" selected, "Execute as" = "Me (`<email>`)", "Who has access" = "Only myself", filled from the manifest. See README step 3.
7. **`clasp create-script` against a local `appsscript.json`**: whether it overwrites the file in `app/`. If it does, the README restores it before `clasp push`. Result 2026-11-18 (clasp 3.4.1): it does overwrite it, with a default manifest and no scopes or `webapp` block. The README restores the file before `clasp push`.
8. **`create-script` honours `--project`.** Result 2026-11-18 (clasp 3.4.1): it writes the named file and leaves `.clasp.json` alone, but only when the file already exists (`{}` is enough) and only with an absolute path, see Upkeep.
9. **`clasp list-deployments`** is the clasp v3 name, and its output shows the ID that `update-deployment` takes. Result 2026-11-18: confirmed. Each line is `<deploymentId> @<version>`, with an `@HEAD` line. `update-deployment <deploymentId>` printed "Redeployed `<deploymentId>` @4" and kept the ID.
10. **`SpreadsheetApp.getActiveSpreadsheet()`** returns the bound sheet inside a web app call, under the `spreadsheets.currentonly` scope. If not, widen to `spreadsheets`.
11. **`ScriptApp.getService().getUrl()`** gives the `/exec` URL from a menu dialog, and what it gives before any deployment. Result 2026-11-18: from a menu dialog it gives a `/exec` URL with an ID that matches no deployment, and the page says "Sorry, unable to open the file at this time." on both the PMLE and PDE sheets. `doGet` now saves the URL in the script property `web_app_url`, the menu reads that, and the link then opens the app. Before the first open of the web app the property is empty. See [Menu](#menu).
12. **Plain-text format on a tab** keeps `2.10`, `TRUE` and ISO timestamps as strings when the app writes them with `setValues`.

## Out of scope

- **A user override of a tag on a scraped row.** Parked in the interview log. It waits for evidence that wrong tags hurt the sampler or a **Study guide** chapter.
- **Study guide chapters in the app.** Chapters stay md files in v1 (D144).
- **More than one user per deployment** (D18).
- **A pass mark** (D184). Google publishes no pass score.
- **A final-week mode and interval compression** (D174, D177). The exam-date cap covers it.
- **Deleting a past test** (D285). `Attempts` rows are never edited.
- **A snapshot of the previous bank, and a new / changed diff** (D204).
- **A script-driven import.** File > Import is the only path (ADR 0003).
- **Editing the Copy prompt template in Settings** (D264).
- **Another SR algorithm.** `Attempts` allows a later replay into one (D165).
- **A lock on Review mode during a test** (D185).
- **Withdrawing a Report** `[G10]`.

## Decision gaps

The user confirmed every default below on 2026-11-17. They are decisions D362 to D378 in `interview-log.md`, G1 as D362 through G17 as D378.

- **G17, D378: small wording and timing choices.** No decision gives these, and the spec picks one each: the 10 second lock wait and "The sheet is busy. Try again."; "Exam is today" on the exam day; a dismissed banner returns on the next page load; the refusal, warn, wipe and stop texts; the troubleshooting line for a code change that does not show; "repeat steps 2 to 4" after a sheet copy; `clasp list-deployments` in the update steps.

Noted, left as decided:

- **Level sentences name "Google Cloud ML"** (D262). They fit PMLE and read wrong for another exam. D264 keeps the template a code constant, so a second exam needs a code edit or a later decision.

A later spec review settled six more points, D388 to D393, cited by D-number where they apply: one unfinished **Mock Test** status and no `resumeMockTest()` (D388), **Review mode** lists and the **Section** breakdown built on the server (D389), `My answer: none (skipped)` (D390), the answer-letter check on `active` rows only (D391), filter counts sent by the server (D392), no `pauseMockTest()` (D393).
