# 08: Go public, with history and content audit

Spec: [0001, Notes and License](../../../docs/specs/0001-exam-bank-skill.md#7-notes-and-license), [0001, Visual rules](../../../docs/specs/0001-exam-bank-skill.md#visual-rules). Log: RV-D4.

**What to build:** `Gjandane/gcp-exam-builder` is public. Nothing in its tree or history republishes question-site content, and the user has decided how to handle site names in code and docs.

**Blocked by:** 06, 07

**Status:** wontfix

**Model tier:** heavy
**Effort:** high
**Where:** cli
**Constraints:** Only the user flips visibility, in GitHub Settings. The agent never rewrites history or force-pushes without the user's explicit yes in chat. Real banks under `exam-bank/` stay gitignored.

Findings (2026-11-18, `git grep` and `git log --all`):

- Test fixtures saved from question sites are tracked. They likely hold real questions: `scripts/tests/fixtures/examtopics/page-1.html` (18 KB), `examtopics/gate.html`, `certsafari/practice-questions.html` (in history), `merge/sources/*.jsonl`, `export/bank.jsonl`, `export/pmle-questions.csv`.
- Site names appear in 24 tracked files: the scrapers (`scrapers/examtopics.py`, `certsafari.py`), their tests, `steps/02-scrape.md`, `pmle.example.yaml`, spec 0001, and tickets 08 to 10 of `exam-bank-skill`.
- History also holds `reference_pictures/` (screenshots of site pages) and `.scratch/gcp-exam-sim/research/certsafari-pmle.md`, which are no longer tracked.

Decisions for the user (triage):

1. Fixtures: replace each site-saved page with synthetic markup that has the same structure and invented questions, so parser tests still pass?
2. History: publish a fresh single-commit repo, rewrite this one with `git filter-repo`, or publish history as it is?
3. Site-named scrapers in a public repo: keep them as they are, or move them out and keep only the generic LLM-scrape path?
4. `.scratch/`: publish the effort folders, or untrack them?

- [ ] User has answered decisions 1 to 4 (record them in the comments)
- [ ] Fixtures replaced per decision 1; the full check suite passes
- [ ] History handled per decision 2
- [ ] Scrapers and `.scratch/` handled per decisions 3 and 4
- [ ] Final sweep: `git grep` and `git log --all -p` show no copied question text
- [ ] User: set visibility to public, then upload the social preview and About text from ticket 07

**Verify:**

- `python scripts/check.py` passes
- A fresh clone of the public repo, searched for question text from the real bank, returns nothing
- The README renders on github.com while logged out

## Comments

- 2026-11-18, decisions (user, in chat): 1 yes, replace site-saved fixtures with synthetic pages of the same structure. 2 fresh single-commit public repo from the cleaned tree; this private repo stays as the archive, no history rewrite, no force-push. 3 keep the site-named scrapers. 4 publish `.scratch/`.

- 2026-11-18: Superseded by tickets 13, 14, 15, 16 (readme-visuals RV-D26). The agent now does every capture and GitHub action; the user only approves.
