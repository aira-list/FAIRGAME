# Architecture

This document describes the runtime layout of FAIRGAME and the responsibilities
of each module. It is the canonical reference for engineers extending the
framework — for end-user instructions see [`../README.md`](../README.md).

## High-level data flow

```
┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐    ┌────────────────┐
│ JSON config  │ →  │  IoManager +     │ →  │ FairGameFactory   │ →  │ FairGame loop  │
│ + template   │    │  ConfigValidator │    │ (permutations,    │    │ (rounds,       │
│              │    │  (Pydantic)      │    │  agents, games)   │    │  stop checks)  │
└──────────────┘    └──────────────────┘    └───────────────────┘    └────────────────┘
                                                                              │
                                                                              ▼
                                                              ┌────────────────────────────┐
                                                              │ ResultsProcessor → CSV /   │
                                                              │ S3-compatible bucket       │
                                                              └────────────────────────────┘
```

Two parallel paths drive the engine:

* **CLI** (`main.py`): loads a JSON config + a prompt template, calls the
  factory directly (`local`) or via HTTP (`web`).
* **Web** (`fairgame_web.py`): a FastAPI app exposing the engine behind
  `/api/runs` (plus presets, run history, CSV download, translation,
  health) and serving a vanilla SPA from `web/` at `/`.

## Module responsibilities

| Module | Role |
|---|---|
| `src/fairgame.py` | `FairGame` orchestrator: round loop, stop conditions, descriptive snapshot. |
| `src/game_round.py` | `GameRound`: prompt build, communication phase, strategy selection (with retry). |
| `src/payoff_matrix.py` | `PayoffMatrix`: combination → weight resolution, score attribution; lazy O(1) reverse cache. |
| `src/prompt_creator.py` | Template fill: handles optional intro / opponent / round-length blocks and the choose/communicate phase blocks. |
| `src/agent.py` | `Agent`: thin wrapper around an LLM connector with strategy + score history. |
| `src/fairgame_factory.py` | `FairGameFactory`: load config, expand permutations, build `FairGame`s, run them. Houses `FakeCommunicationConfig`. |
| `src/fake_message_generator.py` | Random decimal/hex strings used in the optional fake-communication phase. |
| `src/io_managers/io_manager.py` | Routes config + template loads through `FileManager` and `ConfigValidator`. |
| `src/io_managers/configuration_validator.py` | Pydantic v2 schema + cross-field validation. |
| `src/io_managers/payoff_matrix_transformer.py` | Tolerates the legacy `[strategy, weight]` payoff format and rewrites it. |
| `src/io_managers/file_manager.py` | JSON / `.txt` / `.rtf` reading; CSV writing. |
| `src/llm_connectors/` | Provider connectors (OpenAI, Anthropic, Mistral) and the `ChatModelFactory`. |
| `src/results_processing/` | Flatten run output into a `pandas` DataFrame for CSV / S3. |
| `src/template_translation/` | Placeholder-preserving translation pipeline. |
| `src/utils/logger.py` | Centralized logging configuration. |
| `src/utils/utils.py` | Slug / dedup / path helpers. |

## LLM connectors

```
┌────────────────────────┐
│ AbstractConnector      │  retries (tenacity), env-driven backoff
└─────────▲──────────────┘
          │
   ┌──────┴────────┐
   ▼               ▼               ▼
Anthropic     Mistral        OpenAI
Connector     Connector      Connector
```

* **`AbstractConnector`** wraps `_send_prompt` in a tenacity `Retrying`
  loop. Subclasses widen `RETRYABLE_EXCEPTIONS` to declare which provider
  errors should be retried.
* **`ChatModelFactory`** maps logical model names (e.g. `OpenAIGPT4o`) to a
  concrete connector class via `MODEL_PROVIDER_MAP`. Connector classes are
  loaded **lazily** — a missing SDK only fails when its model is actually
  selected, so e.g. tests can run without `mistralai` installed.
* **`register_model(name, cls, provider_model)`** lets tests substitute a fake
  connector at runtime. The session-scoped fixture in
  `unit_tests/conftest.py` uses this to drive the entire suite without live
  network access.
* **Retry tuning** — `FAIRGAME_LLM_MAX_ATTEMPTS`, `FAIRGAME_LLM_BACKOFF_MIN`,
  `FAIRGAME_LLM_BACKOFF_MAX`. Strategy-selection retries are tuned separately
  via `FAIRGAME_STRATEGY_MAX_ATTEMPTS`.

## Permutation semantics

`FairGameFactory` expands a config along three axes:

1. Agents (the names list).
2. Personalities (per-language list).
3. `opponentPersonalityProb` values.

When **every agent uses the same LLM**, symmetric permutations are deduped
(`itertools.combinations_with_replacement`) so that e.g. (cooperative,
selfish) and (selfish, cooperative) collapse into a single game. With mixed
LLMs the factory falls back to `itertools.product` to preserve agent identity.

This dedup is *intentional* — it cuts the run-time cost of bias studies that
would otherwise re-run a symmetric pair under both orderings.

## Configuration validation

`ConfigValidator.validate_config_structure()` is the single boundary that
typed Pydantic data flows through. After this point, the rest of the codebase
can rely on:

* booleans being real booleans (no `_str2bool` needed),
* `payoffMatrix` having the canonical four-block shape (`weights`,
  `strategies`, `combinations`, `matrix`),
* `llm` and `llms` being mutually exclusive,
* `templateFilename` and `promptTemplate` being mutually exclusive.

If the legacy `[strategy, weight]` matrix shape is passed in, the
`PayoffMatrixTransformer` rewrites it before validation succeeds.

## Logging

All modules log via `src.utils.logger.get_logger(__name__)`. The first call
configures the root logger at the level of `FAIRGAME_LOG_LEVEL` (default
`INFO`) and silences noisy third-party loggers (`urllib3`, `botocore`,
`httpx`, …). Application entry points (`fairgame_web.py`, `main.py`)
call `configure_logging()` explicitly to lock in the format early.

There are no `print` statements left in the runtime path.

## Backwards compatibility shims

* `src/llm_factory_connector.py` — re-exports the unified module and emits a
  `DeprecationWarning`.
* `FairGame.print_game_info` — alias of the new `log_game_info`.
* `FairGameFactory._resolve_llms_for_agents` — accepts a bare LLM string for
  legacy test fixtures that pass a model identifier where a config dict is
  expected.

These shims exist for migration and may be removed in a future release.
