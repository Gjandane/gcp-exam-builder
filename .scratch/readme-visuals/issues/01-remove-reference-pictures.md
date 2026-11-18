# 01: Remove reference_pictures

Spec: [0001, README parts](../../../docs/specs/0001-exam-bank-skill.md#readme-parts). Log: RV-D4.

**What to build:** The tracked `reference_pictures/` folder is gone from the working tree, so no file name in the repo names a question site. History is not rewritten.

**Blocked by:** none

**Status:** resolved

**Model tier:** light
**Effort:** low
**Where:** cli
**Constraints:** `git rm` only. Do not commit `certsafari-live-temp.html`. No history rewrite.
**Prerequisite:** yes

- [x] `reference_pictures/` removed with `git rm -r`
- [x] No other file references it (grep)

**Verify:**

- `git ls-files reference_pictures` prints nothing
- Checks in `docs/checks.md` pass
