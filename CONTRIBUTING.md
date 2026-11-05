# Contributing to Echo-Path

A short guide so we don't overwrite each other's work before the deadline.

## Setup and run

Requires Python 3.11 or newer.

```powershell
cd "NASA Project"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows you can also double-click `NASA Project/Start Echo-Path.bat`. The app opens at http://127.0.0.1:8501.

## Test before you push

From `NASA Project/`:

```powershell
python -m unittest discover -s tests -v
```

All tests should pass. GitHub runs the same tests on every push and pull request to `main` (see the **Actions** tab). A red ❌ next to a commit means something broke.

## Workflow

1. **Pull first:** run `git pull` before you start, so you're working on the latest version.
2. **Small changes** (typos, doc wording) can go straight to `main`.
3. **Code changes** (anything in `app.py`, `echo_path/` or `tests/`) go on a branch:
   ```powershell
   git switch -c yourname/short-topic
   # ...make changes, run the tests...
   git push -u origin yourname/short-topic
   ```
   Open a pull request on GitHub, wait for the check to go green, then merge.
4. **Say what you're editing.** Before you start on a file, post it in the team chat, especially for `app.py` and the Paper. Two people editing the same file at once is what causes merge conflicts.

## Don't commit

- **Large DEM files:** keep sample crops under about 5 MB, and for full LOLA products link to the source instead.
- **Cache files:** `__pycache__/` and `*.pyc` (already in `.gitignore`).
- **Personal tool folders:** editor or app settings such as `.obsidian/`, `.vscode/` or `.idea/`.

## Where things live

| Path | What it is |
|---|---|
| `web/` | 3D lander + rover app (Vite + React + Three.js); see `web/README.md` |
| `NASA Project/api/` | FastAPI server the 3D app calls |
| `Dockerfile`, `DEPLOY.md` | The live demo: how it's built and deployed |
| `NASA Project/app.py` | Streamlit dashboard |
| `NASA Project/echo_path/` | Engine modules: terrain, comms, trajectory, routing, rover, evaluation, export |
| `NASA Project/tests/` | Engine and dashboard tests |
| `NASA Project/MODEL_GUIDE.md` | Model assumptions, shown in the app's "Data & model guide" tab |
| `NASA Project/NASA Space Apps 2026 - Paper.md` | Paper draft |
| `README.md` | Full project documentation |
| `FEEDBACK.md` | Open issues with the docs and paper |
