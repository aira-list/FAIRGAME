# FAIRGAME — A Framework for AI Agents Bias Recognition using Game Theory

FAIRGAME runs game-theoretic simulations between LLM-powered agents to surface
biases tied to language, personality, and strategy. It supports classical
scenarios (Prisoner's Dilemma, Volunteer's Dilemma, Battle of the Sexes) and
custom payoff matrices, expanding any scenario across personalities, opponent
priors, languages, and provider mixes.

Developed by the AI Readiness and Assessment (AIRA) group at the Luxembourg
Institute of Science and Technology — part of the
[AI Sandbox](https://ai-sandbox.list.lu/).

## Features

* **Configurable scenarios** — JSON describes agents, payoff matrix, prompts,
  and stop conditions.
* **Multi-provider LLM connectors** — OpenAI, Anthropic Claude, Mistral. Add
  more by registering a connector class.
* **Permutation engine** — automatic expansion across personality and prior
  combinations, with symmetric dedup when every agent shares an LLM.
* **Multilingual** — prompts can ship in any language, and an LLM-driven
  translator preserves placeholders while validating semantic similarity.
* **Theory-of-Mind toolkit** — belief elicitation phase, ToM-order ablation,
  private agent types, Brier-score metrics. See
  [`docs/THEORY_OF_MIND.md`](docs/THEORY_OF_MIND.md).
* **Game-theoretic toolkit** — mixed strategies, discount factor, indefinite
  horizon, utility transforms (CRRA, Fehr-Schmidt), canonical baselines
  (TFT, GrimTrigger, …), round-robin tournaments, equilibrium / welfare
  metrics, multi-seed runs with confidence intervals, and an experiment
  manifest runner. See [`docs/GAME_THEORY.md`](docs/GAME_THEORY.md).
* **Production hardened** — Pydantic-validated config, structured logging,
  retry/timeout on LLM calls, FastAPI/uvicorn HTTP layer, hardened
  Dockerfile, Helm chart.
* **Web app + REST API** — FastAPI backend at `/api/*` plus a vanilla
  Tailwind+Alpine SPA at `/`. Design experiments without writing JSON,
  run them on real or simulated agents, and download results. Demo
  mode lets you preview every feature without a single API key. See
  [`docs/GUI.md`](docs/GUI.md).

## Repository layout

```
web_api/              # FastAPI app: REST API + static SPA mount (web_api.main:app)
web/                  # Vanilla SPA (Tailwind + Alpine via CDN)
main.py               # CLI runner (local or via API)
Dockerfile            # Production container, runs as non-root with healthcheck
pyproject.toml        # Packaging + tool config (ruff, mypy, pytest)
src/                  # Engine source code
  fairgame.py            # Top-level orchestrator
  fairgame_factory.py    # Permutation expansion + game construction
  game_round.py          # Single-round flow with retry/parsing
  phases.py              # Per-round phases (communication, trust, beliefs, choose)
  payoff_matrix.py       # Combination -> weight resolution
  prompt_creator.py      # Template fill (intro/opponent/length/phase blocks)
  agent.py               # LLM-backed and baseline participants
  io_managers/           # Config + file IO + Pydantic validation
  llm_connectors/        # Unified LiteLLM connector + factory
  results_processing/    # Result-row builder (row_schema.py = column contract)
  template_translation/  # Placeholder-preserving translation pipeline
  utils/                 # Logger + helpers
starter_library/      # Shipped defaults (game types, templates, configs) seeded on first run
  game_types/         # One JSON per game type
  templates/          # One Markdown-frontmatter file per prompt template
  configurations/     # One JSON per ready-to-run configuration
unit_tests/           # Test suite; no LLM credentials required by default
docs/                 # ARCHITECTURE / CONFIGURATION / DEPLOYMENT / GAME_THEORY
```

## Quick start

```bash
python -m venv fairenv
source fairenv/bin/activate
pip install -e '.[server,test]'
cp .env.example .env
# Fill in OPENAI_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY as needed.

# Two ways to drive FAIRGAME:

# 1) Web app — FastAPI backend + vanilla SPA (recommended for everyone):
uvicorn web_api.main:app --reload --port 4263
# Then open http://localhost:4263  (4263 = "GAME" on a phone keypad).
# Demo mode is on by default — no API keys needed to explore.

# 2) The CLI (one config per invocation; see python main.py --help):
python main.py local prisoner_dilemma/prisoner_dilemma_round_known_conventional
```

> The CLI and other paper tooling read example configs/templates from the
> sibling `Fairgame_paper_evaluations/resources/` folder (override with the
> `FAIRGAME_RESOURCES_DIR` environment variable). The web app itself needs no
> `resources/` — it ships its defaults in `starter_library/`.

The web app exposes the same engine as a REST API, so you can drive it
programmatically too:

```bash
# Run a shipped configuration by id (the offline baseline needs no API keys):
curl -X POST http://localhost:4263/api/configurations/seed_cfg_pd_baseline_tournament/run

# ...or run an inline config:
curl -X POST http://localhost:4263/api/runs \
     -H 'Content-Type: application/json' \
     -d '{"config": { /* game config */ }}'
```

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

## Tests

```bash
pytest                              # no LLM access needed (deterministic fake)
FAIRGAME_LIVE_LLM=1 pytest          # also exercises live translation tests
pytest --cov=src --cov-report=term-missing
```

The suite uses a deterministic fake LLM connector registered by
`unit_tests/conftest.py`. Set `FAIRGAME_LIVE_LLM=1` to opt back into the
provider-dependent tests (translation, end-to-end via real APIs).

## Docker

```bash
docker build -t fairgame:dev .
docker run --rm -p 4263:4263 \
  -e OPENAI_API_KEY=sk-... \
  fairgame:dev
```

The image runs uvicorn as a non-root `fairgame` user on port 4263 and exposes
an `/api/health` endpoint used by the built-in HEALTHCHECK.

## Documentation

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module map, data flow,
  retry/permutation/logging design.
* [`docs/GUI.md`](docs/GUI.md) — FastAPI web UI (SPA) walkthrough.
* [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — every JSON field, every
  env var, the canonical and legacy payoff-matrix shapes.
* [`docs/GAME_THEORY.md`](docs/GAME_THEORY.md) — mixed strategies, baselines,
  tournaments, discount factor, equilibrium / welfare metrics, multi-seed
  runs, experiment manifest.
* [`docs/THEORY_OF_MIND.md`](docs/THEORY_OF_MIND.md) — belief elicitation,
  ToM-order ablation, private types, Brier-score metrics.
* [`docs/ROADMAP.md`](docs/ROADMAP.md) — game-theoretic features we have
  *not* yet shipped, with rationale and design sketches.
* [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — local / Docker / Helm /
  production checklist / observability.

## Required environment

See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md#environment-variables)
for the full list. The minimum:

* `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` and/or `MISTRAL_API_KEY` —
  required for the providers you actually use (LiteLLM reads the
  provider-standard variable names). Unused providers need no key.

Run results are persisted locally under `results/web/<run_id>/`.

## Governance & contributing

Development follows the rules in [`GOVERNANCE.md`](GOVERNANCE.md). Participation
implies agreement with the [Code of Conduct](CODE_OF_CONDUCT.md). For
contributions, read [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
