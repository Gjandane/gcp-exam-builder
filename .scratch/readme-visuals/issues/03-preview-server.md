# 03: App preview server

Spec: [0002, Visuals, app side](../../../docs/specs/0002-study-app.md#visuals-app-side). Log: RV-D7, RV-D8.

**What to build:** One command starts a local server that shows the real study app screens in a browser. The fake adapter backs it, seeded with the **Demo bank**. No Google deployment.

**Blocked by:** 02

**Status:** resolved

**Model tier:** standard
**Effort:** medium
**Where:** cli
**Constraints:** Lives under `scripts/`. Reuse `app/tests/load-server.js`, `fake-adapter.js` and `bank-fixture.js`. Change no app code. One fake adapter per session, so state carries between calls. Fixed, sensible `now`.

- [x] Serves `app/client/index.html` with the 7 `include_` scriptlets inlined
- [x] A Proxy stub for `google.script.run` posts each call to `/rpc/<fn>` and calls the success or failure handler
- [x] Seeded with the Demo bank and valid Settings, so the home screen loads, not the refused screen
- [x] **Review mode**, **Mock Test**, results and history work end to end
- [x] A smoke test covers it within the checks in `docs/checks.md`

**Verify:**

- Start it, open each screen, answer a Review question and finish a Mock Test with no console errors
- Checks in `docs/checks.md` pass

## Comments

- 2026-11-18: `scripts/preview_app.js` (`node scripts/preview_app.js`, port 8787). Clock starts 2026-11-18T09:00Z and follows real time. `PREVIEW_CLOCK_CONTROL=1` adds `POST /dev/advance?days=N`, used only by the capture script. Menu items return 404.
- `app/tests/preview.test.js` smoke test runs in `npm test`. Walked home, Review mode, Mock Test, results and history in the browser pane with no console errors.
- `.claude/launch.json` entry `app-preview` added for the desktop preview pane (local, untracked).
