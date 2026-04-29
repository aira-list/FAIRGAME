# Game-theoretic features

This page is the canonical reference for the game-theoretic capabilities
that ship with FAIRGAME. Each section covers what the feature does, the
config field that turns it on, the columns it adds to the results
DataFrame, and a short pointer to a worked example.

For Theory-of-Mind features (belief elicitation, types, recursive belief
prompts, Brier score) see [`THEORY_OF_MIND.md`](THEORY_OF_MIND.md).

For features we have *not* yet implemented, with the rationale and a
design sketch, see [`ROADMAP.md`](ROADMAP.md).

## At a glance

| Feature | Config field(s) | Adds columns / outputs |
|---|---|---|
| Mixed strategies | `mixedStrategies: true` | `agentN_mixed_distribution_per_round` (in history) |
| Discount factor | `discountFactor: 0.9` | applies to every recorded score |
| Indefinite horizon | `continuationProbability: 0.95` | rounds past the first end stochastically |
| Utility transforms | `utilityTransform: { type: ..., ... }` | applies to recorded scores |
| Equilibrium metrics | `equilibria: ["combination4", ...]` or `"auto"` | `equilibrium_rate`, `equilibrium_per_round`, `first_equilibrium_round` |
| Welfare metrics | (automatic) + `paretoOptimalSum` | `welfare_mean_sum`, `welfare_mean_min`, `welfare_mean_gini`, `welfare_efficiency`, `welfare_per_round` |
| Regret tracking | (automatic) | `agentN_regret_per_round`, `agentN_regret_mean` |
| Reputation placeholders | optional `reputationWindow: int`; template uses `{coopRateN}` / `{reputationN}` | rolling cooperation rate per opponent injected into the prompt |
| Hypothesis testing | `compare_metric` / `compare_metrics` | Welch t-test + Mann-Whitney U for any two runs |
| Canonical baselines | `llms: {agent: "Baseline:Name"}` | non-LLM agents used as controls / tournament entries |
| Round-robin tournaments | `tournament: { enabled: true }` | NC2 pair games per scenario |
| Deterministic replay | `seed: 42` | same seed → identical run |
| Multi-seed + CIs | `seedCount: 5` (or `seeds: [...]`) | `<metric>_mean`, `<metric>_ci_half_width` (after `aggregate_seeds`) |
| Experiment manifest | top-level `manifest.json` | per-config CSV + aggregated CSV + `manifest_summary.json` |
| Cross-run comparison | GUI page **⚖️ Compare runs** | overlaid charts + per-metric Welch / Mann-Whitney p-values |

## 1 — Mixed strategies

When `mixedStrategies: true`, the agent is asked for a probability
distribution over the strategies (instead of a single label) and the engine
samples one action from that distribution.

* Add a `{mixedChoose}: [ ... ]` block to your prompt template; ask the
  agent to output JSON of the form `{"<strategy1_label>": p1, ...}`.
* The same JSON parser as belief elicitation handles the response — small
  rounding errors are silently re-normalised.
* The history record gains a `mixed_distribution` field per round in
  addition to the realised `strategy`.
* Sampling uses the game's seeded RNG, so reruns with the same `seed`
  produce identical realisations.

Example: [`unit_tests/config/prisoner_dilemma_mixed.json`](../unit_tests/config/prisoner_dilemma_mixed.json).

## 2 — Discount factor

`discountFactor: δ ∈ (0, 1]` multiplies each round's payoffs by
``δ^(round-1)`` *before* they are written into agent history. δ=1 is the
classical undiscounted setting; δ<1 reproduces the standard
infinite-horizon repeated-game model.

Discount is applied **after** any utility transform, so the order is
``raw_payoff → utility → × δ^(t-1)``.

## 3 — Indefinite horizon (continuation probability)

`continuationProbability: p ∈ (0, 1]` — after the first round, each
subsequent round is played with probability `p` and skipped otherwise.
This implements the stochastic-termination model that supports cooperation
in finitely-repeated games via folk-theorem-style arguments.

The check uses the game's seeded RNG, so multi-seed runs vary the realised
horizon while keeping a single run reproducible.

## 4 — Utility transforms

`utilityTransform: { type: ..., ... }` applies a utility function to the
vector of agents' raw payoffs each round.

* `{ "type": "CRRA", "gamma": 0.5, "offset": 1.0 }` — constant relative
  risk aversion. ``γ=0`` is risk-neutral (affine); ``γ=1`` is the log
  case; higher γ is more risk-averse. ``offset`` is added to each payoff
  before the transform so zero/negative payoffs don't break the log/power.
* `{ "type": "FehrSchmidt", "alpha": 0.4, "beta": 0.6 }` — inequity
  aversion: ``u_i = x_i − α·(envy term) − β·(guilt term)``.
* `{ "type": "identity" }` — no change (default).

Add new transforms by subclassing
``src.utility.UtilityTransform`` and adding the class to
``_TRANSFORM_REGISTRY``.

## 5 — Equilibrium-distance metrics

`equilibria: ["combination4", "combination1"]` declares which combination
keys count as equilibria for the purposes of analysis. The results
DataFrame then gains:

* `equilibrium_per_round` — list of `{True, False, None}` per round.
* `equilibrium_rate` — fraction of resolved rounds at equilibrium.
* `first_equilibrium_round` — 1-based round of the first equilibrium hit, or `null`.

Useful for studying convergence to e.g. the all-defect Nash in PD.

## 6 — Welfare metrics

Whenever a game runs, the results DataFrame gains:

* `welfare_per_round` — list of `{sum, mean, min, max, gini}` per round.
* `welfare_mean_sum` — mean of round-sums (utilitarian welfare).
* `welfare_mean_min` — mean of round-mins (Rawlsian welfare).
* `welfare_mean_gini` — mean Gini coefficient.

If you set `paretoOptimalSum: <number>`, an extra
`welfare_efficiency` = mean(round-sum) / paretoOptimalSum
column is emitted. Values close to 1 mean the agents are fully realising
the available joint surplus.

The Gini implementation shifts non-positive payoffs by a small constant
so the metric is well-defined even with zero or negative payoffs.

## 7 — Canonical strategy library (baselines)

A first-class set of non-LLM strategies is available via
``Baseline:<Name>`` model identifiers in the `llms` config block:

| Identifier | Behaviour |
|---|---|
| `Baseline:AlwaysCooperate` | Always plays the *cooperate* strategy. |
| `Baseline:AlwaysDefect` | Always plays the *defect* strategy. |
| `Baseline:Random` | Uniform over all strategies. |
| `Baseline:TitForTat` | Cooperate first, then mirror the opponent's most recent action. |
| `Baseline:GrimTrigger` | Cooperate until any opponent has *ever* defected, then defect forever. |
| `Baseline:RandomMixed(strategy1=0.7,strategy2=0.3)` | Sample from the supplied fixed distribution. |

The "cooperate" / "defect" semantics are configurable per game with
`baselineSemantics: { "cooperate": "strategy1", "defect": "strategy2" }`.
By default the first strategy key counts as cooperate and the last as
defect.

Baselines are useful as:

* **controls** — compare LLM agents against a population of well-known
  benchmark strategies;
* **tournament entries** — see below;
* **opponents** — pin one slot to a baseline and study how an LLM responds
  to a known fixed strategy.

## 8 — Round-robin tournaments

Setting

```json
"tournament": { "enabled": true, "mode": "round_robin", "symmetric": true }
```

instructs the factory to generate one game per *unordered pair* of agents
in `agents.names`, instead of one big game with all agents. Each pair
inherits the rest of the config (LLM assignments, types, ToM order,
discount factor, …).

For 3 agents this yields 3 pair games (`a×b`, `a×c`, `b×c`); for 6 agents
it yields 15.

A typical tournament config combines `tournament` with the canonical
strategy library:

```json
"agents": { "names": ["alwaysC", "alwaysD", "tft", "grim"], ... },
"llms": {
  "alwaysC": "Baseline:AlwaysCooperate",
  "alwaysD": "Baseline:AlwaysDefect",
  "tft":     "Baseline:TitForTat",
  "grim":    "Baseline:GrimTrigger"
}
```

See [`unit_tests/config/prisoner_dilemma_tournament.json`](../unit_tests/config/prisoner_dilemma_tournament.json).

## 9 — Deterministic replay

Every source of randomness in FAIRGAME (type draws, fake messages,
mixed-strategy sampling, baseline `Random`/`RandomMixed`,
indefinite-horizon continuation checks) goes through a private
`random.Random` instance. Setting `seed: 42` in the config seeds it; two
runs with the same seed and identical inputs produce byte-identical
histories *for the parts under the engine's control* (LLM calls
themselves are not deterministic unless the provider supports it).

Internally the seed flows through ``FairGameFactory._create_single_game``
into ``FairGame.rng``; tests may also pass `rng=` directly to ``FairGame``.

## 10 — Multi-seed runs and confidence intervals

Three top-level fields, in priority order:

* `seeds: [0, 1, 2, 3, 4]` — explicit list.
* `seedCount: 5` — auto-generate `[seed, seed+1, ..., seed+4]` (or
  `[0, ..., 4]` if `seed` is unset).
* `seed: 42` — single-seed shorthand.

When more than one seed is requested, the factory runs the full
``create_games → run_games`` pipeline once per seed, tags every game with
its seed (``game_id`` is prefixed with ``seedN_``), and merges the
results.

The companion helper
``src.results_processing.seed_aggregator.aggregate_seeds(df)`` collapses
the per-seed DataFrame into one row per (language × personality × LLM)
configuration with ``<metric>_mean`` and ``<metric>_ci_half_width``
columns. CIs are 95% Normal-approximation by default; pass
``confidence=0.90`` for narrower windows.

## 11 — Experiment manifest

For multi-config studies (e.g. a ToM-order ablation across three configs
with five seeds each), a manifest bundles them into one run:

```json
{
  "experiment_name": "tom_ablation",
  "output_dir": "results/tom_ablation",
  "configs": ["pd_tom0.json", "pd_tom1.json", "pd_tom2.json"],
  "seeds": [0, 1, 2, 3, 4],
  "aggregate_seeds": true,
  "config_overrides": { "nRounds": 10 }
}
```

Run it with:

```bash
python -m src.experiment manifest.json
```

The runner writes one ``<config>_per_seed.csv`` (raw rows) and one
``<config>_aggregated.csv`` (mean + 95% CI) per config, plus a
``manifest_summary.json`` listing every output file.

## Worked recipes

* **Risk-aversion bias study** — set `utilityTransform.gamma` to a sweep
  of values; observe how cooperation rates shift across LLM × personality
  cells.
* **Folk-theorem demonstration** — set `discountFactor: 0.95`,
  `continuationProbability: 0.95`, run with `nRounds: 50`, and check
  whether the LLM cooperation rate exceeds the one-shot Nash baseline.
* **TFT calibration** — fix `agent2` as `Baseline:TitForTat` and run an
  LLM as `agent1`; if the LLM is rational it should learn to cooperate
  within a few rounds.
* **Welfare audit by language** — same scenario across `languages: [en,
  fr, ar, cn, vn]` with `paretoOptimalSum` set; compare
  `welfare_efficiency` per language.

## Files

* `src/utility.py` — utility-function transforms.
* `src/baseline_strategies.py` — canonical non-LLM strategies.
* `src/results_processing/game_metrics.py` — equilibrium + welfare math.
* `src/results_processing/seed_aggregator.py` — multi-seed CIs.
* `src/experiment.py` — manifest runner.
* `src/utils/rng.py` — deterministic RNG plumbing.
