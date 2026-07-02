# Roadmap

Game-theoretic features that we have *not* yet implemented in FAIRGAME,
with the rationale for deferring them and a design sketch for whoever
picks them up next. See [`GAME_THEORY.md`](GAME_THEORY.md) for what's
already shipped.

The items below are ordered by my (subjective) sense of research leverage
vs. implementation cost.

## 1 — Continuous / parameterised action spaces

**Why deferred** — the entire payoff representation assumes a finite
strategy enum. Cournot, Bertrand, public-goods contributions, ultimatum
*amount*, auction *bids*: none are expressible.

**Design sketch** — Introduce a `payoff_function: { type: "callable",
module: "...", name: "..." }` alternative to `payoffMatrix`. The callable
takes a tuple of agent actions (each a float or vector) and returns a
tuple of payoffs. Strategy parsing in `GameRound` becomes "parse a number
from the response" with bounds and tolerance. ToM blocks remain.

## 2 — Extensive-form / sequential games

**Why deferred** — current engine is strictly simultaneous-move. Anything
with information sets (ultimatum, alternating-offer bargaining,
centipede, signaling games) needs a game tree.

**Design sketch** — Add `game_form: "normal" | "extensive"` and an
`extensive_form: { nodes: [...], decision_points: [...], chance_nodes:
[...] }` schema. `GameRound` becomes a tree-walker that prompts the
agent at the next decision node and routes per response. Reuse the
existing prompt-block mechanism for per-node prompts.

## 3 — Equilibrium computation

**Why deferred** — rolling our own Nash / mixed-Nash / correlated
equilibrium solvers is fraught. ``nashpy`` and ``gambit`` already do this
well.

**Design sketch** — Add an optional `nashpy` dependency. Expose
``src.results_processing.equilibrium.compute_nash_equilibria(payoff_matrix)``
that returns a list of equilibrium strategy profiles. Then declare
**`equilibria: "auto"`** in the config, and the analysis layer fills in
the equilibrium list automatically before computing
`equilibrium_rate`.

## 4 — Replicator dynamics / evolutionary game theory

**Why deferred** — needs a population module distinct from the
single-game loop. Heavy dependency on `numpy` for fast iteration.

**Design sketch** — A new `src/evolutionary/` package with a population
state vector, replicator update step, and ESS detection. Plug
existing `BaselineStrategy` instances in as the population members.
Drive it via a separate manifest type (`type: "evolutionary"`).

## 5 — Learning baselines (Q-learning, fictitious play, no-regret)

**Why deferred** — needs a cross-round agent memory protocol that is
currently absent (LLMs are stateless across rounds; baselines have
implicit memory hard-coded in their `choose` method).

**Design sketch** — Promote `BaselineStrategy.choose` to also take a
mutable per-agent memory dict. Implement
``QLearningAgent`` (ε-greedy over a tabular Q on the strategy enum),
``FictitiousPlay`` (track empirical opponent distribution and best-respond),
``RegretMatching`` (Hart-Mas-Colell). All become first-class baselines
in the existing registry.

## 6 — Bargaining protocols

**Why deferred** — Rubinstein alternating offers and friends are
extensive-form games; depends on item 2.

**Design sketch** — Once extensive-form support lands, ship Rubinstein,
Nash bargaining, and Kalai-Smorodinsky as scenario presets in
`starter_library/configurations/`.

## 7 — Auctions

**Why deferred** — same as 1+2 (continuous bids + sequential ascending
clocks).

**Design sketch** — Each auction format is a small extensive-form scenario;
generic continuous-action support unblocks first-price, second-price, all-pay
without specialised code. English/Dutch need a clock event loop —
implement as a thin wrapper around extensive form.

## 8 — Matching markets

**Why deferred** — Gale-Shapley is not a game in the strategic sense; it's
a procedure. Wider scope than the rest of FAIRGAME.

**Design sketch** — Add `src/matching/` with deferred-acceptance and
top-trading-cycles implementations; treat agent preferences as the
"strategy" they reveal.

## 9 — Power analysis

**Why deferred** — needs a statistical *recommendation* engine, not just
code. Choosing target effect sizes, MDE, sample sizes, etc., is
research-judgment territory.

**Design sketch** — `src.factory.experiment.power_analysis(manifest, target_effect,
target_power)` returns a recommended `seedCount`. Use Welch t-tests over
the seed-aggregated DataFrame; punt on more sophisticated designs.

## 10 — Reputation / public history aggregation

**Why deferred** — touches every prompt template; needs careful UX
design to avoid bloating prompts beyond LLM context windows.

**Design sketch** — Compute per-agent reputation each round (e.g. share
of cooperative actions) and inject as `{reputation_<name>}` placeholders.
Add a `reputation_window: int` to bound the lookback.

## 11 — N-player generalisation of the payoff format

**Why deferred** — the current `combinations` schema scales as `|S|^N`
which becomes unwieldy past 4 players. Many N-player games (public
goods, tragedy of the commons) have a closed-form payoff function
instead.

**Design sketch** — Same as item 1 — once we accept callable payoff
functions, N-player setups stop being a config-size problem.

## 12 — Cooperative (coalitional) games

**Why deferred** — completely orthogonal mode of play; needs a
characteristic function v(S) and Shapley / nucleolus solvers.

**Design sketch** — `src/cooperative/` with a `CharacteristicFunction`
class and Shapley-value / core / nucleolus computations. Game flow
becomes "form coalitions, split surplus" rather than "play strategies".

---

If you want to pick up one of these, the existing
`src/agents/baseline_strategies.py` and `src/results_processing/game_metrics.py`
are good models for how to add a new analysis layer without touching the
core engine.
