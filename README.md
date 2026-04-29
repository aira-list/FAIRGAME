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
fairgame_web.py       # FastAPI app: REST + static SPA mount
web/index.html        # Single-file vanilla SPA (Tailwind + Alpine via CDN)
main.py               # CLI runner (local or via API)
Dockerfile            # Production container, runs as non-root with healthcheck
pyproject.toml        # Packaging + tool config (ruff, mypy, pytest)
src/                  # Engine source code
  fairgame.py            # Top-level orchestrator
  fairgame_factory.py    # Permutation expansion + game construction
  game_round.py          # Single-round flow with retry/parsing
  payoff_matrix.py       # Combination -> weight resolution
  prompt_creator.py      # Template fill (intro/opponent/length/phase blocks)
  agent.py               # LLM-backed participant
  fake_message_generator.py
  io_managers/           # Config + file IO + Pydantic validation
  llm_connectors/        # OpenAI / Anthropic / Mistral + factory
  results_processing/    # DataFrame builder for CSV / S3 output
  template_translation/  # Placeholder-preserving translation pipeline
  utils/                 # Logger + helpers
resources/
  config/             # Example scenario configs
  game_templates/     # Per-language prompt templates
unit_tests/           # 54 tests; no LLM credentials required by default
docs/                 # ARCHITECTURE / CONFIGURATION / DEPLOYMENT
```

## Quick start

```bash
python -m venv fairenv
source fairenv/bin/activate
pip install -e '.[server,test]'
cp .env.example .env
# Fill in API_KEY_OPENAI, API_KEY_ANTHROPIC, API_KEY_MISTRAL as needed.

# Two ways to drive FAIRGAME:

# 1) Web app — FastAPI backend + vanilla SPA (recommended for everyone):
uvicorn fairgame_web:app --reload
# Then open http://localhost:8000.
# Demo mode is on by default — no API keys needed to explore.

# 2) The CLI:
python main.py local
```

The web app exposes the same engine as a REST API, so you can drive it
programmatically too:

```bash
curl -X POST http://localhost:8000/api/runs \
     -H 'Content-Type: application/json' \
     -d '{"preset": "prisoner_dilemma/prisoner_dilemma_round_known_conventional", "demo_mode": true}'
```

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

## Tests

```bash
pytest                              # 54 tests, no LLM access needed
FAIRGAME_LIVE_LLM=1 pytest          # also exercises live translation tests
pytest --cov=src --cov-report=term-missing
```

The suite uses a deterministic fake LLM connector registered by
`unit_tests/conftest.py`. Set `FAIRGAME_LIVE_LLM=1` to opt back into the
provider-dependent tests (translation, end-to-end via real APIs).

## Docker

```bash
docker build -t fairgame:dev .
docker run --rm -p 5003:5003 \
  -e API_KEY_OPENAI=sk-... \
  fairgame:dev
```

The image runs gunicorn as a non-root `fairgame` user and exposes a
`/health` endpoint used by the built-in HEALTHCHECK.

## Documentation

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module map, data flow,
  retry/permutation/logging design.
* [`docs/GUI.md`](docs/GUI.md) — Streamlit web UI walkthrough.
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

* `API_KEY_OPENAI` and/or `API_KEY_ANTHROPIC` and/or `API_KEY_MISTRAL` —
  required for the providers you actually use. Connectors load lazily, so an
  unused provider does not need a key.
* Optional: `S3_ENDPOINT`, `BUCKET_NAME`, `S3_KEY`, `S3_SECRET`, `S3_PREFIX`,
  `DEFAULT_FOLDER` to persist results.

## Governance & contributing

Development follows the rules in [`GOVERNANCE.md`](GOVERNANCE.md). Participation
implies agreement with the [Code of Conduct](CODE_OF_CONDUCT.md). For
contributions, read [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
