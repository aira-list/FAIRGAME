# Web app walkthrough

FAIRGAME ships with a FastAPI backend that serves both a REST API
(`/api/...`) and a small vanilla-JavaScript SPA (`/`). It's intended
for non-technical users — researchers, analysts, students — who want
to design experiments without reading the JSON schema, *and* for
machine clients that want to drive the engine programmatically.

## Running it

```bash
pip install -e '.[server,test]'
uvicorn web_api.main:app --reload
```

The app binds to port `4263` by default ("GAME" on a phone keypad). Open
<http://localhost:4263>. Auto-reload picks up edits to either the
backend (`web_api/`) or the frontend (`web/index.html`).

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

Pick a shipped configuration from the library — the starter library
(`starter_library/`) seeds a set of ready-to-run scenarios on first
launch. Click **Run** and the result table renders inline once the
engine returns. The CSV is also downloadable.

### 🛠️ Scenario builder

Start from a shipped configuration (or a blank one), edit the JSON
inline, click **Run**. (Form-based builder is on the roadmap; for now
the JSON view is the most flexible way to tweak any field.)

### 📊 Results

Browse every run on this machine in newest-first order. Each run
displays its metadata (timestamp, demo/live, n games) plus the
per-game DataFrame.

## REST API

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/health` | GET | Liveness probe |
| `/api/configurations` | GET | List shipped + user configurations |
| `/api/configurations/{id}/run` | POST | Run a stored configuration and persist results |
| `/api/runs` | POST | Run an inline config and persist results |
| `/api/runs` | GET | List past runs |
| `/api/runs/{id}` | GET | Detail for one run (metadata + rows) |
| `/api/runs/{id}/csv` | GET | Download the run's CSV |
| `/api/templates/{id}/translate` | POST | AI-translate a stored template into target languages |

## What's stored where

```
results/web/
  <run_id>/                # 12-char hex id assigned at run time
    metadata.json          # request config + timestamp + demo flag
    results.csv            # ResultsProcessor DataFrame
```

## Limits and roadmap

* The web app calls the engine in-process. For long multi-seed
  tournaments, prefer the experiment-manifest runner
  (`python -m src.experiment <manifest.json>`).
* Runs are synchronous — long requests hold the connection open. A
  Server-Sent Events progress endpoint and per-run status polling
  are on the roadmap.
* No authentication / multi-tenancy. The app is built for local
  research use; if you need to expose it remotely, deploy behind an
  SSO proxy (see [DEPLOYMENT.md § Security](DEPLOYMENT.md#security)).
* The SPA loads its libraries from CDNs. Alpine and Chart.js are pinned
  with Subresource Integrity hashes, but Tailwind uses the runtime JIT
  build (`cdn.tailwindcss.com`, unpinned) and fonts come from Google
  Fonts. For production or offline use, replace the runtime Tailwind CDN
  with a pre-built local stylesheet and self-host the fonts.
* The configuration builder's serialize (`buildConfig`) and deserialize
  (`applyConfigToBuilder`) logic in `web/js/app.configurations.js` is split
  into focused, per-field-group `_serialize*` / `_hydrate*` helpers. The
  module is still large overall, and a small SVG-graph helper is duplicated
  with `app.results.js` — both remain minor known tech debt.
