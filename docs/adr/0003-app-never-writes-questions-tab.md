# The app never writes to the Questions tab

The study app reads the `Questions` sheet tab and never writes to it. Everything the app records (attempts, spaced-repetition state, Bookmarks, notes, Mock Tests, Reports, settings) lives in other tabs, keyed by the frozen question ID ([ADR 0001](0001-question-id-frozen-at-first-merge.md)).

A new Question bank reaches the sheet through File > Import, which replaces the whole `Questions` tab. Any app column there would be wiped on each re-import. We considered a script-driven import that merges new rows into the tab and keeps app columns. We dropped it because it makes every re-import a merge with its own failure modes, and it ties app history to row position.

Within the app tabs, the append-only `Attempts` log is the source of truth. Spaced-repetition box, due date and counters are a cache the app can rebuild from it.

## Consequences

- A re-import into the `Questions` tab cannot damage app data. An app row whose ID is gone from `Questions` stays in its tab.
- One Import option, "Replace spreadsheet", replaces every tab and so wipes app data. The app keeps a "set up" mark outside the sheet; when the mark exists but `Attempts` is missing, it stops and points to version history instead of recreating empty tabs.
- The app joins by `id` on every load. It never relies on row order in `Questions`.
- No app data rides in the bank CSV; the 30-column schema stays the skill's alone.
- A lost or corrupt state tab is repairable by replaying `Attempts`. A later move to another algorithm replays the same log.
- An `Attempts` row is never edited or re-graded after it is written.
