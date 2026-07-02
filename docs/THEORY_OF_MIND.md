# Theory of Mind in FAIRGAME

This page documents the Theory-of-Mind (ToM) features added to FAIRGAME. See
[`docs/CONFIGURATION.md`](CONFIGURATION.md) for full schema details.

## Why ToM?

Game-theoretic outcomes hinge on what each player *believes* about the others.
Many results — Nash equilibria of asymmetric-information games, signaling
equilibria, the unraveling of finitely-repeated cooperation — only fall out
when players reason at second order or higher ("what does my opponent think
*I* will do?"). FAIRGAME originally had a single static prior
(`opponentPersonalityProb`) and no way to elicit, score, or vary the order of
reasoning. The features described here close that gap.

## Feature overview

| Feature | Config field | Effect |
|---|---|---|
| Belief elicitation | `elicitBeliefs: true` | Adds a `believe` phase before each `choose` phase. The agent must output a JSON probability distribution over the opponent's strategies. |
| ToM-order ablation | `tomOrder: 0 \| 1 \| 2` | Controls which information about the opponent appears in the rendered prompt. |
| Private agent types | `agents.types` | Draws a private type for each agent from a prior; injected into the prompt via `{ownType}`. |
| Common-knowledge prior | `typesAreCommonKnowledge: true` | Adds a `{typeDistribution}` placeholder visible to both agents. |
| Belief-accuracy metrics | (automatic when beliefs are elicited) | Brier score, modal-strategy agreement rate, and `p(realised outcome)` per agent per game. |

## Prompt template extensions

Templates can opt into new block markers. All are optional — pre-existing
templates work unchanged at `tomOrder: 1`.

```
{secondOrder}: [Remember that {opponent1} is also reasoning about you.]
{ownType}: [Your private type is "{ownType}". Your opponent does not know this.]
{believe}: [Before choosing, predict {opponent1}'s strategy as JSON: {{"{strategy1}": 0.X, "{strategy2}": 0.Y}}. Output ONLY the JSON.]
{choose}:  [Choose between {strategy1} and {strategy2}. Output ONLY the choice.]
```

ToM-order semantics:

* `tomOrder=0` — `{opponentIntro}` is stripped regardless of personality data;
  `{secondOrder}` is stripped.
* `tomOrder=1` — `{opponentIntro}` is included when the opponent has a
  meaningful personality / prior; `{secondOrder}` is stripped. (Default;
  legacy behaviour.)
* `tomOrder=2` — `{opponentIntro}` included; `{secondOrder}` block kept.

The phase router (`{communicate}`, `{believe}`, `{choose}`) keeps only the
block matching the active phase and removes the others.

## Belief format and parsing

Beliefs are JSON objects mapping each strategy label (or canonical key) to a
probability:

```json
{"Cooperate": 0.7, "Defect": 0.3}
```

`src.agents.belief_parser.parse_belief` is tolerant of:

* prose surrounding the JSON object,
* canonical keys (`"strategy1"`) or display labels (`"Cooperate"`),
* small (≤5%) deviations from a sum of 1.0 — re-normalised silently,
* missing strategies — filled with zero probability.

The parser rejects negative probabilities, unparseable JSON, sums that are
implausibly far from 1, and responses that mention no recognised strategy.
Parse failures retry up to `FAIRGAME_BELIEF_MAX_ATTEMPTS` times (default 3);
on final failure the round records `belief: null` and the game continues.

## Belief metrics

When beliefs are elicited, every per-agent row in the results DataFrame gains:

| Column | Definition |
|---|---|
| `agentN_beliefs` | List of per-round belief distributions. |
| `agentN_belief_brier_per_round` | List of multi-class Brier scores (lower is better; 0=perfect, 2=maximally wrong). |
| `agentN_belief_mean_brier` | Mean Brier across rounds with valid beliefs and observed opponent strategies. |
| `agentN_belief_mean_p_outcome` | Mean stated probability of the realised opponent strategy. |
| `agentN_belief_agreement_rate` | Fraction of rounds where the modal-probability strategy matched reality. |

For >2 agents, each round's metric is averaged across opponents.

## Example

The shipped `seed_cfg_pd_tom` configuration
(`starter_library/configurations/05-seed_cfg_pd_tom.json`) is a two-agent
Prisoner's Dilemma at `tomOrder=2` with belief elicitation, a binary type
system (`trusting` vs `cynical`) drawn from a uniform prior, and the prior
declared common knowledge.

```bash
# Run the shipped ToM configuration by id (live models need the relevant
# provider API key):
curl -X POST http://localhost:4263/api/configurations/seed_cfg_pd_tom/run
```

## Research recipes

* **ToM-order ablation study** — run the same scenario at `tomOrder=0/1/2`
  with `elicitBeliefs=true` and compare cooperation rates and Brier scores.
* **Bayesian-game baseline** — set `agents.types`, `typesAreCommonKnowledge=true`,
  and template `{ownType}` / `{typeDistribution}` blocks to test whether the
  LLM uses the announced prior to update beliefs across rounds.
* **Calibration audit** — run any cooperative scenario with
  `elicitBeliefs=true` and inspect `belief_mean_p_outcome` per language /
  personality cell to detect over-/under-confidence biases.
* **Deception probe** — set `agentsCommunicate=true` together with
  `elicitBeliefs=true` to compare the messages an agent sends with the
  beliefs its opponent forms — the gap is a first-pass deception score.

## Limitations

* Beliefs are scored against opponents' single revealed action per round, so
  the metrics are noisy for very short games.
* Types are drawn at game-start and held constant — there is no mid-game
  update mechanism (the rules of a fully-Bayesian update would have to be
  encoded in the prompt template).
* The current `believe` phase asks for first-order beliefs only. Eliciting
  second-order beliefs ("what does your opponent predict you'll do?") is
  possible by extending the template, but no first-class support yet exists
  for scoring such elicitations.
