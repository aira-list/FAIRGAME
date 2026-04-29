# Configuration reference

A FAIRGAME run is described by a single JSON document. This page is the
canonical reference for every field accepted by the validator
(`src/io_managers/configuration_validator.py`).

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | str | yes | Display name; used in result filenames. |
| `nRounds` | int | yes | Maximum number of rounds. |
| `nRoundsIsKnown` | bool | yes | If `true`, the round count is injected into the prompt. |
| `languages` | `list[str]` | yes | BCP-47 language codes; each must appear in `agents.personalities` and `payoffMatrix.strategies`. |
| `agentsCommunicate` | bool | yes | Enable the per-round inter-agent message phase. |
| `allAgentPermutations` | bool | yes | When `true`, expand all personality / opponent-prob permutations. |
| `agents` | object | yes | See [Agents](#agents). |
| `payoffMatrix` | object | yes | See [Payoff matrix](#payoff-matrix). |
| `stopGameWhen` | `list[str]` | yes | List of combination keys (e.g. `combination4`) that stop the game early. |
| `llm` | str | one of | Single model name applied to every agent. |
| `llms` | `list[str]` or `dict[str, str]` | one of | Per-agent model assignment. List length must match `len(agents.names)`; dict keys must equal `agents.names`. |
| `promptTemplate` | `dict[str, str]` | one of | Inline `{lang: text}` template; mutually exclusive with `templateFilename`. |
| `templateFilename` | str | one of | Stem of a file under `resources/game_templates/{name}_{lang}.txt`. |
| `fakeCommunication` | bool | no | Replace real inter-agent messages with random tokens. Default `false`. |
| `fakeMessageCount` | int | no | Number of fake messages per agent per round (default `1`). |
| `fakeMessageBase` | `"dec"` \| `"hex"` | no | Encoding of the fake messages (default `"dec"`). |
| `elicitBeliefs` | bool | no | Run a `believe` phase before each `choose` phase; the agent is asked to predict its opponent's strategy as JSON probabilities. Default `false`. |
| `tomOrder` | `0` \| `1` \| `2` | no | Theory-of-Mind order injected into prompts: `0` strips opponent info; `1` keeps it (default); `2` also keeps the `{secondOrder}` block. |
| `typesAreCommonKnowledge` | bool | no | When `agents.types` is set, surface the *prior distribution* (not the realised type) to opponents. Default `false`. |
| `mixedStrategies` | bool | no | Ask the agent for a probability distribution and sample. Default `false`. |
| `reputationWindow` | int | no | Number of recent rounds used to compute `{coopRateN}` / `{reputationN}` template placeholders. Omit for full-history average. |
| `discountFactor` | float | no | δ ∈ (0, 1] applied to payoffs each round. Default `1.0`. |
| `continuationProbability` | float | no | Indefinite-horizon termination probability per round (after round 1). |
| `utilityTransform` | object | no | Maps raw payoffs to utilities. See [`GAME_THEORY.md`](GAME_THEORY.md). |
| `equilibria` | `list[str]` or `"auto"` | no | Combination keys declared as equilibria, or the string `"auto"` to compute pure-strategy Nash equilibria via nashpy at validation time. |
| `paretoOptimalSum` | float | no | Reference sum used in the welfare-efficiency metric. |
| `seed` | int | no | Master seed for deterministic replay. |
| `seedCount` | int | no | Re-run the pipeline this many times with distinct seeds. |
| `seeds` | `list[int]` | no | Explicit seed list (takes precedence over `seedCount`). |
| `tournament` | object | no | `{ enabled, mode, symmetric }` — round-robin pairwise games. |
| `baselineSemantics` | `{ cooperate, defect }` | no | Tells the canonical strategy library which keys mean cooperate / defect. |

`llm` and `llms` are mutually exclusive. `promptTemplate` and
`templateFilename` are mutually exclusive.

## Agents

```json
"agents": {
  "names": ["agent1", "agent2"],
  "personalities": {
    "en": ["cooperative", "selfish"],
    "fr": ["coopératif", "égoïste"]
  },
  "opponentPersonalityProb": [0, 50],
  "types": {
    "labels": ["trusting", "cynical"],
    "probs": [0.5, 0.5],
    "commonKnowledge": false
  }
}
```

* `names` — at least 2 entries; ordered.
* `personalities[lang]` — must contain exactly `len(names)` entries per
  language listed in `languages`.
* `opponentPersonalityProb` — required when `allAgentPermutations: false`,
  with one entry per agent. Otherwise it is interpreted as the *value pool*
  to permute over.
* `types` *(optional)* — Bayesian-game type system; each agent draws a
  private label from `labels` according to `probs` (uniform when omitted).
  See [`THEORY_OF_MIND.md`](THEORY_OF_MIND.md).

## Payoff matrix

The canonical shape contains four blocks:

```json
"payoffMatrix": {
  "weights":      { "weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2 },
  "strategies":   { "en": { "strategy1": "OptionA", "strategy2": "OptionB" } },
  "combinations": {
    "combination1": ["strategy1", "strategy1"],
    "combination4": ["strategy2", "strategy2"]
  },
  "matrix": {
    "combination1": ["weight1", "weight1"],
    "combination4": ["weight4", "weight4"]
  }
}
```

A legacy compact form is also accepted (each combination listed as
`[strategy, weight]` pairs); it is transformed automatically by
`PayoffMatrixTransformer` before validation continues.

## Environment variables

| Name | Default | Purpose |
|---|---|---|
| `API_KEY_OPENAI` | — | Required for OpenAI connector. |
| `API_KEY_ANTHROPIC` | — | Required for Anthropic connector. |
| `API_KEY_MISTRAL` | — | Required for Mistral connector. |
| `FAIRGAME_LOG_LEVEL` | `INFO` | Root logger level. |
| `FAIRGAME_LLM_MAX_ATTEMPTS` | `3` | Retry attempts for transient LLM errors. |
| `FAIRGAME_LLM_BACKOFF_MIN` | `1.0` | Min seconds between retries. |
| `FAIRGAME_LLM_BACKOFF_MAX` | `10.0` | Max seconds between retries. |
| `FAIRGAME_STRATEGY_MAX_ATTEMPTS` | `10` | Times to re-prompt an agent when its response fails to parse. |
| `FAIRGAME_BELIEF_MAX_ATTEMPTS` | `3` | Retries when an agent's belief JSON cannot be parsed. |
| `FAIRGAME_TRANSLATOR_MODEL` | `OpenAIGPT4o` | Model used by the translation endpoint. |
| `FAIRGAME_LIVE_LLM` | unset | Set to `1` in tests to opt-in to live-LLM tests. |
| `S3_ENDPOINT` / `BUCKET_NAME` / `S3_KEY` / `S3_SECRET` / `S3_PREFIX` | — | S3-compatible upload (skipped if any are missing). |
| `DEFAULT_FOLDER` | `fairgame-results` | Top-level prefix used when constructing result keys. |
| `FAIRGAME_URL` | `http://127.0.0.1:5003/create_and_run_games` | Endpoint used by `main.py` in `api` mode. |
| `PORT` | `5003` | Bind port for the dev server. |

## Example

The shipped example
[`resources/config/prisoner_dilemma/prisoner_dilemma_round_known_conventional.json`](../resources/config/prisoner_dilemma/prisoner_dilemma_round_known_conventional.json)
is a single-round Prisoner's Dilemma with cooperative/selfish personalities
across five languages, scored against a standard four-cell payoff matrix.

## Shipped scenarios

The 2×2 social-dilemma family ported from the Fairgame paper evaluations:

| Scenario | Path | Notes |
|---|---|---|
| Prisoner's Dilemma | `prisoner_dilemma/prisoner_dilemma_round_known_conventional.json` | Defection is the unique Nash. |
| Stag Hunt | `stag_hunt/stag_hunt_round_known.json` | Two pure equilibria — payoff-dominant vs risk-dominant. |
| Snowdrift (Chicken) | `snow_drift/snow_drift_round_known.json` | Anti-coordination; equilibria at the off-diagonal cells. |
| Harmony Game | `harmony_game/harmony_game_round_known.json` | Cooperation strictly dominates — benign benchmark. |
| Battle of the Sexes | `battle_sexes/battle_sexes_round_known.json` | Asymmetric coordination. |
| Zero-Sum Matching | `zero_sum/zero_sum_round_known.json` | Strictly competitive; mixed-strategy equilibrium. |
| Volunteer's Dilemma | `unit_tests/config/volunteer_dilemma_*.json` | N-player; permutation stress-test. |

Each is selectable from the GUI's Quick start page or referenced directly via the API / CLI.

### Covert / random / fake communication channels

For every 2×2 social dilemma above, a *covert communication* family lives
under `resources/config/<game>/covert/`:

| Channel | Behaviour | Template |
|---|---|---|
| `covert_dec` | Agents must encode messages as 10 decimal numbers (≤3 digits) | `<game>_covert_dec_en.txt` |
| `covert_hex` | Same with hexadecimal digits | `<game>_covert_hex_en.txt` |
| `random_dec` | Control: agents are *told* to output a random decimal sequence | `<game>_random_dec_en.txt` |
| `random_hex` | Random control with hex digits | `<game>_random_hex_en.txt` |
| `fake_dec` / `fake_hex` | Engine generates the noise via `fakeCommunication: true` | (no template needed) |

Regenerate the entire family from scratch with:

```bash
python -m tools.generate_covert_configs
```

Useful for paper-style ablation studies: pair each covert config with its
`random` and `fake` controls under one experiment manifest, then compare
cooperation rates to isolate any signal that emerges through the covert
channel.
