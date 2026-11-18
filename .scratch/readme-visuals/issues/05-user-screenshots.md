# 05: User screenshots and masking

Spec: [0001, Visual rules](../../../docs/specs/0001-exam-bank-skill.md#visual-rules), [0002, Visuals, app side](../../../docs/specs/0002-study-app.md#visuals-app-side). Log: RV-D3, RV-D10, RV-D11, RV-D24.

**What to build:** Three real screenshots, masked, in `docs/assets/`: the "Google hasn't verified this app" screen, the New deployment dialog, and the `/exam-bank pmle export` summary.

**Blocked by:** none

**Status:** wontfix

**Model tier:** light
**Effort:** low
**Where:** desktop
**Constraints:** The user captures. The agent crops and masks. Mask the email, avatar, sheet ID, script ID, `/exec` URL, question-site names and local paths.

- [ ] User: screenshot the unverified-app screen (Part 2, step 2) and the New deployment dialog (step 3)
- [ ] User: run `/exam-bank pmle export` and screenshot the summary
- [ ] Agent: crop, mask and optimize all three into `docs/assets/`

**Verify:**

- Zoom into each image: no personal data, no site name

## Comments

- 2026-11-18 (agent): Done: `docs/assets/deploy-dialog.png` (New deployment dialog). Cropped as-is; email in "Execute as" masked with solid fill (was blur, not allowed); optimized; verified by zoom, no personal data or site names.
- Missing, not in repo or in `%USERPROFILE%\Pictures\Screenshots` (folder does not exist): unverified-app screen (Part 2, step 2) and `/exam-bank pmle export` summary. User still to capture both.
- Boxes left unticked: user capture boxes (one combined box is only half met; export box not met); agent box (two images missing). Status unchanged (`ready-for-human`).
- Note: git history at 86f5e61 holds the earlier blur-masked `deploy-dialog.png`; consider a history rewrite before go-public (ticket 08).

## Build notes

- none

- 2026-11-18: Superseded by tickets 09, 10 (readme-visuals RV-D26). The agent now does every capture and GitHub action; the user only approves.
