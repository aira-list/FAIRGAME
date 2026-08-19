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

## Running without API keys

A configuration whose agents are *all* baseline strategies (TFT,
GrimTrigger, AllC, AllD, …) needs no provider keys — the moves are
computed locally, so it runs offline. Configurations backed by LLM
agents require the relevant provider key in the environment (see
[Required environment](../README.md#required-environment)).

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
displays its metadata (timestamp, n games) plus the
per-game DataFrame. A fresh install starts populated: real sample
results for every seed configuration (GPT-4o and Claude Haiku 4.5,
produced by `tools/populate_seed_results.py`) ship in
`starter_library/runs/` and are copied in at startup.

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
    metadata.json          # request config + timestamp
    rows.json              # canonical result rows (native types)
    results.csv            # derived CSV export
```

Shipped sample runs live in `starter_library/runs/` (same layout) and are
topped up into `results/web/` by run id at app startup — user runs are
never touched.

## Limits and roadmap

* The web app calls the engine in-process. For long multi-seed
  tournaments, prefer the experiment-manifest runner
  (`python -m src.factory.experiment <manifest.json>`).
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
