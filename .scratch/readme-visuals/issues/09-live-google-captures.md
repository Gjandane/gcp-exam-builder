# 09: Live Google capture and Try it check

Spec: [0002, Visuals, app side](../../../docs/specs/0002-study-app.md#visuals-app-side), [0002, Try it in 5 minutes](../../../docs/specs/0002-study-app.md#try-it-in-5-minutes), [0001, Visual rules](../../../docs/specs/0001-exam-bank-skill.md#visual-rules). Log: RV-D3, RV-D27, RV-D29, RV-D30, RV-D35.

**What to build:** `docs/assets/unverified-app.png` shows the "Google hasn't verified this app" screen, masked. The Try it path is proven on a real sheet. The old raw captures are gone.

**Blocked by:** none

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** desktop
**Constraints:** Main checkout, never a worktree (needs the gitignored clasp settings and `exam-bank/`). The only session that drives Chrome or the desktop in wave 1. Never touch `app/.clasp.json` or any existing `app/.clasp-*.json`: they point at the user's real sheets. Use a new `app/.clasp-readme.json` with `--project <absolute path>` on every clasp command, as README Upkeep "Add another exam" shows (PowerShell). Restore the manifest with `git checkout -- app/appsscript.json` after `create-script`. The user's only touches: approve tool access, click Advanced and Allow in the OAuth popup, and say yes in chat before the Trash step. Never type a password. Write only `docs/assets/unverified-app.png` and this ticket.

- [x] Throwaway sheet "PMLE demo (readme)" made with `clasp create-script`, code pushed with `push --force`, per README Part 2 step 1
- [x] Authorization triggered from the sheet. The Claude window moved off the popup first. Desktop screenshot of the unverified screen taken; the screenshot blob copied from this session's `tool-results/` folder into `exam-bank/screens/`
- [x] Cropped to the popup; email, avatar and any ID masked with a solid fill (never blur); optimized; saved as `docs/assets/unverified-app.png`
- [x] Try it path on the same sheet: README Part 2 steps 2 to 6 with `docs/demo/demo-bank.csv`, exam name "PMLE (demo)" and the Demo bank `section_weights` line from ticket 02's comments; the home screen loads; one Review question answered and graded
- [x] Any README step that did not match what happened is noted in this ticket's comments, for ticket 16
- [x] After the user's yes: "PMLE demo (readme)" and "Demo screenshots 2" moved to Trash (not deleted forever); `app/.clasp-readme.json` removed; `exam-bank/screens/` deleted

**Verify:**

- Zoom into `unverified-app.png` at full size: no email, avatar, ID or URL with an ID; no text cut off
- `git status` shows only `docs/assets/unverified-app.png` and this ticket changed
- Checks in `docs/checks.md` pass

## Comments

- 2026-11-18, README mismatches for ticket 16:
  - Step 2: "Open study app" after a first sheet's popup was closed unauthorized keeps showing "Authorization required"; closing the popup mid-flow and reopening works. Once authorized, the "Google hasn't verified this app" screen never returns for that script, so a capture needs a fresh script.
  - Step 3: Deploy takes about 5 s and the dialog matches the README text.
  - Step 5: the Sheets import picker has no way to type a path; an agent must inject the file into the picker's hidden file input. A human just clicks Browse. The README text is right for humans.
  - Step 6: pasting the whole line `section_weights: 1:13,2:16,3:21,4:20,5:18,6:13` (prefix included) into Section weights was accepted. Save takes about 10 s with no feedback; the button greys out.
  - Home screen showed "Review mode 0 due" yet "Start review" opened all 25 questions. Fine, but "0 due" may confuse a first-time reader.
- Two throwaway sheets were made because the first one's authorization finished before the warning could be captured. Both went to Trash, with "Demo screenshots 2". An uploaded `demo-bank.csv` file in My Drive (from the import) was left in place.

## Build notes

None.
