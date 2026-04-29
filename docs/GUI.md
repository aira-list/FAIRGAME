# Web app walkthrough

FAIRGAME ships with a FastAPI backend that serves both a REST API
(`/api/...`) and a small vanilla-JavaScript SPA (`/`). It's intended
for non-technical users — researchers, analysts, students — who want
to design experiments without reading the JSON schema, *and* for
machine clients that want to drive the engine programmatically.

## Running it

```bash
pip install -e '.[server,test]'
uvicorn fairgame_web:app --reload
```

The app binds to port `8000` by default. Open
<http://localhost:8000>. Auto-reload picks up edits to either the
backend (`fairgame_web.py`) or the frontend (`web/index.html`).

## Demo mode

The sidebar has a **Demo mode** toggle that defaults to **on**. While
it's on, every LLM call is answered by a fast, deterministic
in-process fake — no API keys are needed and no provider charges
accrue. Switch the toggle off when you're ready to use real models;
you'll see a green "Live mode" banner and provider APIs will be billed
on every agent action.

The toggle is sent on each `POST /api/runs` request, so each run
freshly installs or restores the connector registry.

## Pages

### 🏠 Home

Landing page: cards linking to each workflow plus an embedded guide
(what FAIRGAME does, the three big switches, glossary).

### 🚀 Quick start

Pick a shipped scenario from the dropdown — every JSON file under
`resources/config/<category>/<name>.json` shows up grouped by
category. Click **Run scenario** and the result table renders inline
once the engine returns. The CSV is also downloadable.

### 🛠️ Scenario builder

Pick a preset, edit the JSON inline, click **Run**. (Form-based
builder is on the roadmap; for now the JSON view is the most flexible
way to tweak any field.)

### 📊 Results

Browse every run on this machine in newest-first order. Each run
displays its metadata (timestamp, demo/live, n games) plus the
per-game DataFrame.

## REST API

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | Liveness probe |
| `/api/presets` | GET | List shipped scenarios, grouped by category |
| `/api/presets/{id}` | GET | Load a preset's full JSON config |
| `/api/runs` | POST | Run a config (inline or by preset id) and persist results |
| `/api/runs` | GET | List past runs |
| `/api/runs/{id}` | GET | Detail for one run (metadata + rows) |
| `/api/runs/{id}/csv` | GET | Download the run's CSV |
| `/api/translate` | POST | Translate a prompt template into a target language |

The three Flask paths from the previous version are kept as `308`
redirects: `/health`, `/create_and_run_games`, `/translate_template`
forward to their `/api/*` equivalents.

## What's stored where

```
results/web/
  <run_id>/                # 12-char hex id assigned at run time
    metadata.json          # request config + timestamp + demo flag
    results.csv            # ResultsProcessor DataFrame
```

If `S3_ENDPOINT`, `BUCKET_NAME`, `S3_KEY`, `S3_SECRET` are set in the
environment, the same CSV is also pushed to the configured S3 bucket
under `<DEFAULT_FOLDER>/<models_tag>/<date>_<game>/<file>.csv`.

## Limits and roadmap

* The web app calls the engine in-process. For long multi-seed
  tournaments, prefer the experiment-manifest runner
  (`python -m src.experiment <manifest.json>`).
* Runs are synchronous — long requests hold the connection open. A
  Server-Sent Events progress endpoint and per-run status polling
  are on the roadmap.
* No authentication / multi-tenancy. The app is built for local
  research use; if you need to expose it remotely, deploy behind an
  SSO proxy.
