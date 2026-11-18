# Development checks

From the project folder, install the check dependencies once:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Run the same command used by CI, in bash or PowerShell:

```bash
python scripts/check.py
```

It checks README local links and heading anchors, and rejects configured question-site names and copied permissions. It flags a bare `<placeholder>` outside code in the README or `docs/specs/*.md`, since GitHub hides it. It checks that each copy of the import steps (the README, both specs, `IMPORT_STEPS_` in `app/server/server.js`) equals `templates/import-steps.txt`. Then it runs pytest and the app's `npm test`, both with live output. The script resolves the project from its own location, so it also works when called by absolute path from another folder.

For the doc checks alone, run `python scripts/check.py --readme-only`. For the app tests alone, run `npm test` in `app/`.

CI runs `.github/workflows/check.yml` on pushes and pull requests, using Python 3.11 and Node 22 on Linux and Windows. Fixtures run without Claude credentials or live question sites.

README visuals (spec 0002, Visuals, app side). Not part of the check run:

- `python scripts/build_demo_bank.py` rewrites `docs/demo/demo-bank.csv` from the questions in the script.
- `node scripts/preview_app.js` serves the study app on http://localhost:8787 over the Demo bank, in memory.
- `python scripts/capture_readme.py` records the README GIFs and screenshots into `docs/assets/`. It needs node, ffmpeg and Playwright's Chromium.
- `python scripts/render_export_summary.py [exam]` runs the real `export` (default `pmle`) in the main checkout, masks site names and paths in the text, and writes `docs/assets/export-summary.png`. It refuses, writing nothing, while the bank cannot export. Needs Playwright's Chromium.
- `python scripts/build_social_preview.py` renders `docs/assets/social-preview.png` (1280×640) from a `hero-review.gif` frame, the title and the tagline. It needs Playwright's Chromium.
