# 16: Publish

Spec: [0001, Notes and License](../../../docs/specs/0001-exam-bank-skill.md#7-notes-and-license), [0001, 0 Showcase](../../../docs/specs/0001-exam-bank-skill.md#0-showcase). Log: RV-D31, RV-D32, RV-D36, RV-D37; old ticket 08, decisions 2 to 4.

**What to build:** `Gjandane/gcp-exam-builder` is a public, single-commit repo whose README renders fully for a logged-out visitor, with About, topics and social preview set. The old private repo is `Gjandane/gcp-exam-builder-archive` and holds the full history.

**Blocked by:** 09, 10, 11, 12, 13, 14, 15

**Status:** ready-for-agent

**Model tier:** heavy
**Effort:** high
**Where:** desktop
**Constraints:** Main checkout (the content sweep needs the gitignored real bank). Ask for a yes in chat, one at a time, before each outward action: push, repo rename, repo create, `gh repo edit`, social preview upload. Never force-push, never rewrite history in the archive. Real banks under `exam-bank/`, `certsafari-live-temp.html` and `.claude/settings.local.json` never enter the public repo. Site-named scrapers, specs and `.scratch/` are published as they are (old 08 decisions 3 and 4); the README names no site. The public commit's author and committer email is the account's GitHub noreply address (`<id>+<login>@users.noreply.github.com`, id from `gh api user`), never the local `user.email`.

- [ ] README corrections from ticket 09's comments applied on `readme-visuals`; `python scripts/check.py --readme-only` passes
- [ ] Content sweep on `readme-visuals`: `python scripts/check.py` passes; question stems sampled from `exam-bank/pmle/bank.jsonl` (at least 10) found nowhere in `git grep`; no tracked file is a saved site page
- [ ] Render check while private: push `readme-visuals` to `origin`; in Claude in Chrome, open the branch README on github.com; every image loads, Mermaid renders, every anchor and spec link resolves. Fix and repeat until clean
- [ ] Fast-forward `master` to `readme-visuals`; push `master` to `origin`
- [ ] Rename the private repo to `gcp-exam-builder-archive` (`gh repo rename`); update the main checkout's `origin` URL
- [ ] Build the public tree with `git archive master` into a new folder outside this repo; `git init`, one commit; `gh repo create Gjandane/gcp-exam-builder --public --source <folder> --push`
- [ ] Set About and topics from ticket 11's comments with `gh repo edit`
- [ ] Upload `docs/assets/social-preview.png` in the public repo's Settings via Claude in Chrome (file upload)
- [ ] The public repo's `Checks` workflow run passes (`gh run list` after it finishes; no polling loop)
- [ ] Logged-out check: in the built-in browser pane (not signed in to GitHub), the public README renders with every image and the Mermaid diagram

**Verify:**

- `gh repo view Gjandane/gcp-exam-builder --json visibility,description,repositoryTopics` shows PUBLIC, the About line and the topics
- A fresh clone of the public repo has one commit, and `git grep` finds none of the sampled real-bank stems
- `gh repo view Gjandane/gcp-exam-builder-archive --json visibility` shows PRIVATE
- `git log --format='%ae %ce'` in the public repo shows only the noreply address
