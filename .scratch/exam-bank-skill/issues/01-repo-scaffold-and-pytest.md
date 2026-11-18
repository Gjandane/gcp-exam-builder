# 01: Repo scaffold and pytest

Spec: [0001, Repo layout and install](../../../docs/specs/0001-exam-bank-skill.md#repo-layout-and-install), [Config](../../../docs/specs/0001-exam-bank-skill.md#config), [Tests](../../../docs/specs/0001-exam-bank-skill.md#tests)

**What to build:** A cloned repo installs with two commands and runs an empty test suite green. The skill folder skeleton exists in the layout the spec gives, with both requirements files, the ignore file, the MIT license and the two config templates. The folder becomes a git repository so the ignore rules can be checked.

**Blocked by:** None (can start immediately)

**Status:** resolved

**Model tier:** light
**Effort:** low
**Where:** cli
**Constraints:** No version pins in the runtime requirements. Ship no settings file with permissions. Write no root README here (ticket 14). Make no commit unless the user asks.
**Prerequisite:** yes

- [x] The skill folder skeleton matches the spec's repo layout, with empty placeholders only where a later ticket fills the file
- [x] The runtime requirements file lists the four packages, unpinned. The dev requirements file lists pytest
- [x] The two config templates hold exactly the content the spec's Config section gives
- [x] The ignore file covers the data folder and the local settings file
- [x] The license is MIT
- [x] The folder is a git repository
- [x] The single script entry point exists, parses a command and an exam, and exits non-zero on an unknown command
- [x] pytest collects from the skill's tests folder and passes

**Verify:**

- Install both requirements files with pip, then run `playwright install chromium`. Both finish without error
- Run `pytest` from the repo root. It exits 0
- Create a file under the data folder, run `git status --short`. The file does not show
- Load both templates with a YAML parser. Both parse, and the exam template has 6 Sections and 14 Subdomains

## Build notes

- Modules: none added or removed.
- Interface: `eb.py` command set from the spec Scripts table; known commands exit 1 "not implemented yet".
- Mismatch: `pytest.ini` added at repo root (not in spec layout), since pytest skips `.claude/` by default.
- Mismatch: LICENSE holder is "exam-bank contributors" (`git config user.name` unset). Change if wanted.
- Not committed per Constraints ("no commit unless the user asks"); builder commit step withheld.
