# FAIRGAME — User Guide

This document is a longer companion to the in-app Guide on the Home page.
It covers what FAIRGAME is for, how Templates and Configurations fit
together, every placeholder a Template can contain, and walks through the
five canonical games shipped out of the box.

---

## 1. Purpose

FAIRGAME is a **virtual laboratory for studying how Large Language Model
(LLM) agents behave in classical game-theory scenarios.** You set up a
2-or-more-agent game, fill in the rules and personalities, run it on
real or simulated agents, and read out a structured table of choices,
scores, beliefs and welfare metrics.

The framework was built to answer empirically-grounded questions like:

* Do LLM agents cooperate, or do they exploit each other?
* Does the answer change when the prompt is in French versus English?
* Does a stronger model ("Claude Opus") outsmart a weaker one
  ("Mistral 7B") in a one-shot Prisoner's Dilemma?
* Does explicit Theory-of-Mind reasoning ("they think we will defect")
  shift behaviour?
* What happens when you let agents communicate? When they exchange only
  meaningless number sequences (covert/fake-channel mode)?

You produce a **DataFrame of one row per game**, plus a per-round
history. The Results page renders charts (cooperation rate, score, welfare,
equilibrium rate) automatically.

### Data model — three layers

```
Template             Configuration           Run
(prompt body)        (template + params)     (engine output)

   tag → variation    metadata + game cfg       run id + rows
   per language       (referenced by name)      timestamp
                                                CSV + metadata
```

You write a **Template** once per game family per language. You build a
**Configuration** that points at the right (tag, variation, languages)
and bundles all the engine settings (agents, payoffs, ToM, …). You run
the configuration as many times as you like; each run gets a stable id
and shows up in the Results page with charts.

---

## 2. Templates

### 2.1 What a Template is

A Template is the **prompt body** the agent will see, with placeholders
that the engine substitutes at run time. The Templates page lets you
manage them as a library: tags group families of games, and each tag
holds one or more *variations* (e.g. "classic", "harsh", "with
communication"). Each variation can ship in many languages.

```
Tag: "Prisoner's Dilemma"
 ├── Variation: "classic"
 │    ├── language: en  →  body...
 │    ├── language: fr  →  body... (auto-translated via the AI button)
 │    └── language: cn  →  body...
 └── Variation: "with-communication"
      └── language: en  →  body...
```

When a Configuration runs, the engine looks up the (tag, variation,
language) for each language in the Configuration's language list and
injects the matching body as `promptTemplate[lang]`.

### 2.2 The placeholder language

A Template body is plain text plus two kinds of substitution markers:

#### Plain placeholders `{name}`

Substituted with a string. Strings come from the Configuration, the
payoff matrix, and the per-round state. The most useful ones:

| Placeholder | Meaning | Source |
|---|---|---|
| `{currentPlayerName}` | The agent's own name | `agents.names[i]` |
| `{personality}` | The agent's personality (in the active language) | `agents.personalities[lang][i]` |
| `{opponent1}`, `{opponent2}`, … | Each opponent's name | `agents.names` |
| `{opponentPersonality1}`, … | Each opponent's personality | as above |
| `{opponentPersonalityProbability1}`, … | The probability the opponent really has the stated personality, in 0–100 | `agents.opponentPersonalityProbs * 100` |
| `{strategy1}`, `{strategy2}`, … | Display labels for strategies | `payoffMatrix.strategies[lang]` |
| `{weight1}`, `{weight2}`, … | Numeric payoffs | `payoffMatrix.weights` |
| `{nRounds}` | Total number of rounds | `nRounds` |
| `{currentRound}` | Current round number, 1-indexed | engine state |
| `{history}` | Free-text summary of past rounds | engine state |
| `{coopRate1}`, `{coopRate2}` | Rolling cooperation rate of each opponent (0–100) | engine state, controlled by `reputationWindow` and `reputationApplies` |
| `{reputation1}`, … | Coarse reputation label ("highly cooperative" / "uncooperative" / …) | derived from `coopRateN` |
| `{ownType}` | The agent's private type (Bayesian games only) | `agents.types` |
| `{typeDistribution}` | Prior over opponent types when `typesAreCommonKnowledge: true` | `agents.types.probs` |

#### Conditional blocks `{name}:[...]`

Conditional blocks are square-bracketed sections that survive only when
their condition is met; otherwise they're stripped from the rendered
prompt. The recognised block names:

| Block | Kept when… |
|---|---|
| `{intro}: [...]` | Always kept; you put the agent's identity here. |
| `{opponentIntro}: [...]` | `tomOrder ≥ 1`. Stripped at `tomOrder=0` so the agent has *no* information about the opponent. |
| `{gameLength}: [...]` | `nRoundsIsKnown` is true. Lets you tell the agent how many rounds remain only when that information is supposed to be public. |
| `{communicate}: [...]` | The current phase is the communication phase. Used in templates that have `agentsCommunicate: true`. |
| `{choose}: [...]` | The current phase is the strategy-choice phase. |
| `{believe}: [...]` | The current phase is the belief-elicitation phase (when `elicitBeliefs: true`). |
| `{mixedChoose}: [...]` | The current phase is the mixed-strategy distribution phase. |
| `{secondOrder}: [...]` | `tomOrder ≥ 2`. Used to inject "they are thinking about us" reasoning. |
| `{ownType}: [...]` | The agent has a private type assigned. |

The whole `{name}: [...]` form is consumed; only the inner text remains
when the condition is met.

### 2.3 Tags, variations and languages

* **Tag** — a game family (e.g. `Prisoner's Dilemma`).
* **Variation** — a parameter sub-family inside a tag (`classic`,
  `harsh`, `with-communication`, `mixed-strategies`, …). Two variations
  of the same tag share the framing but differ in what the prompt
  emphasises.
* **Language** — ISO code (`en`, `fr`, `ar`, `cn`, `vn`, plus 25 more
  via the AI translator).

### 2.4 The AI Translate button

For any template, the 🌍 Translate button lets you pick target languages
from a 30-language grid. The configured `TemplateTranslator` (model from
`FAIRGAME_TRANSLATOR_MODEL`, default `OpenAIGPT4o`) renders each one
into a new template under the same tag and variation, with
`source_template_id` linking back. Live LLM credentials are required
(demo mode cannot translate).

---

## 3. Configurations

A Configuration is the **complete description of an experiment** —
everything the engine needs to run a set of games. It bundles:

```
{
  metadata             : { name, tag, variation, languages, id, created_at }
  game_config (engine) : {
    nRounds, nRoundsIsKnown, randomizeBetweenIterations,
    agents: { names, personalities, llmServices, opponentPersonalityProbs, types },
    allAgentPermutations,
    agentsCommunicate, fakeCommunication, fakeMessageCount, fakeMessageBase,
    elicitBeliefs, tomOrder, reputationWindow, reputationApplies,
    typesAreCommonKnowledge,
    mixedStrategies, discountFactor, continuationProbability,
    payoffMatrix: { strategies, weights, combinations, matrix },
    equilibria, paretoOptimalSum,
    utility: { type, gamma|alpha|beta },
    baselineSemantics: { cooperate, defect },
    seed, seedCount, seeds,
    stopGameWhen,
    tournament,
  }
}
```

You build it on the Configurations page using the tabbed form
(Basics / Agents / Theory of Mind / Game theory / Payoff matrix /
Reproducibility / JSON view). Save → it gets a stable id and timestamp
and appears in the saved-list. Run → the engine picks the right template
for each language and produces a Run.

### 3.1 Personality assignment modes

The Agents tab offers two modes:

* **Per agent (positional)** — each agent has its own personality
  string. Two agents → two strings.
* **Pool with permutations** — define a *list* of personality strings
  (the pool) and a list of opponent-prior probabilities. The engine
  emits `allAgentPermutations: true`, and the
  `PermutationExpander` generates one game per (n-agent) permutation
  drawn from the pool. With pool size *k* and *n* agents you get up to
  *k<sup>n</sup>* games (or fewer when same-LLM agents trigger
  combinations-with-replacement).

### 3.2 Communication styles

A single dropdown drives three engine fields:

| Style | `agentsCommunicate` | `fakeCommunication` | `fakeMessageBase` |
|---|---|---|---|
| None | false | false | — |
| Real | true | false | — |
| Fake (decimal) | false | true | `dec` |
| Fake (hexadecimal) | false | true | `hex` |

In real mode the LLM emits free-text messages; in fake mode it emits
strings of random numbers — useful for testing covert-channel
information leakage.

### 3.3 Theory of Mind

* `elicitBeliefs` — adds a `believe` phase per round; the agent emits a
  JSON probability distribution over the opponent's strategies; we
  measure Brier score afterwards.
* `tomOrder` — 0/1/2:
  * 0: opponent personality / prior is suppressed from the prompt.
  * 1: opponent personality / prior is shown (default).
  * 2: same as 1, plus a `{secondOrder}` block telling the agent the
    opponent is also reasoning about it.
* `reputationWindow` — number of past rounds shown as `{coopRateN}` /
  `{reputationN}`. Leave 0 to show the full history.
* `reputationApplies` — when False, those reputation placeholders fill
  with `n/a` / `unknown` regardless of history. Use this for asymmetric
  coordination games like Battle of the Sexes, where strategy1 doesn't
  mean "cooperate".

### 3.4 Game-theoretic extensions

* `discountFactor δ ∈ (0, 1]` — multiplies each round's payoff by
  δ<sup>round-1</sup>.
* `continuationProbability ∈ (0, 1]` — at each round end, the game
  continues with this probability (stochastic horizon).
* `equilibria` — list of combination keys you declare to be equilibria,
  or the literal `"auto"` for nashpy-computed pure Nash.
* `paretoOptimalSum` — sum of payoffs at the Pareto-optimal cell. When
  set, the welfare report emits an efficiency ratio.
* `mixedStrategies` — agents return a probability distribution; the
  engine samples and records both the distribution and the realised
  action.
* `utilityTransform` — Identity / CRRA(γ, offset) / Fehr-Schmidt(α, β)
  applied per round to every agent's raw payoff.
* `baselineSemantics: {cooperate, defect}` — required when you mix
  baseline strategies (TitForTat, GrimTrigger, …) into a non-PD game,
  so the baseline knows which of your custom strategy keys is "cooperate".

### 3.5 Payoff matrix editor

The Payoff matrix tab lets you:

1. Edit the **strategy list** (key + display label).
2. For every row × column combination, set the **two payoff numbers**
   (agent 1's, agent 2's).

At save time the editor interns distinct payoff values into weight keys
and emits the canonical engine schema:

```json
{
  "weights":      {"weight1": 3, "weight2": 5, "weight3": 0, "weight4": 1},
  "strategies":   {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
  "combinations": {
    "combination1": ["strategy1", "strategy1"],
    "combination2": ["strategy1", "strategy2"],
    "combination3": ["strategy2", "strategy1"],
    "combination4": ["strategy2", "strategy2"]
  },
  "matrix": {
    "combination1": ["weight1", "weight1"],
    "combination2": ["weight3", "weight2"],
    "combination3": ["weight2", "weight3"],
    "combination4": ["weight4", "weight4"]
  }
}
```

For 3+ agents the JSON view tab lets you write the full schema by hand.

### 3.6 Reproducibility

* `seed` — master seed; same seed → identical run.
* `seedCount` — engine-side multi-seed averaging *within* a single run;
  produces aggregated mean ± 95% CI columns.
* The Experiments page adds a separate **Iterations per config** that
  runs the configuration N times back-to-back (each one is a separate
  Run with its own id and an offset seed).

---

## 4. Walkthrough — the FULLY-FEATURED Prisoner's Dilemma template

The classic shipped template uses about half of what the engine
recognises. Here is a Prisoner's Dilemma template that exercises
**every** placeholder and **every** conditional block. Use it as the
ceiling: a real-life template will usually use only a subset, but if
you want to switch on (say) Theory-of-Mind order 2 plus belief
elicitation plus a real communication phase plus reputation labels plus
private types — the prompt needs all the corresponding markup or those
features have nothing to fill.

```
You are {currentPlayerName} and your opponent is {opponent1}.

{intro}: [
You are {personality}.
{ownType}: [Your private type is {ownType}; this fact is not visible to {opponent1}.]
]

{opponentIntro}: [
{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.
{opponent1}'s rolling cooperation rate over recent rounds is {coopRate1}, which we summarise as: {reputation1}.
The prior over types in this population is: {typeDistribution}.
]

{secondOrder}: [
Be aware: {opponent1} is also reasoning about you, knows that you are reasoning about them, and may try to anticipate your move.
]

You and {opponent1} are arrested for a crime and held in separate cells.

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds in total.]
The current round is number {currentRound}.

If you both choose {strategy1}, you both get a payoff of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get {weight3} and {opponent1} gets {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get {weight2} and {opponent1} gets {weight3}.
If you both choose {strategy2}, you both get a payoff of {weight4}.

This is the history of the choices made so far: {history}.

{communicate}: [
Before choosing this round, send {opponent1} a short free-text message that may help you coordinate. They will see it before they choose.
Output ONLY the message text — no quotes, no labels.
]

{choose}: [
Your goal is to maximise your payoff.
Choose between {strategy1} and {strategy2}.
Output ONLY the choice.
]

{mixedChoose}: [
Your goal is to maximise your expected payoff.
Output a JSON object that gives the probability you assign to each strategy, summing to 1.
Example: {"{strategy1}": 0.7, "{strategy2}": 0.3}
Output ONLY the JSON.
]

{believe}: [
Before you choose this round, predict what {opponent1} is about to do.
Output a JSON object with the probability you assign to each of their strategies, summing to 1.
Example: {"{strategy1}": 0.4, "{strategy2}": 0.6}
Output ONLY the JSON.
]
```

### 4.1 Section-by-section breakdown

#### Identity (always kept)

```
You are {currentPlayerName} and your opponent is {opponent1}.
```

| Placeholder | What it becomes | Source |
|---|---|---|
| `{currentPlayerName}` | the agent's own name, e.g. `"agent1"` | `agents.names[i]` |
| `{opponent1}`, `{opponent2}`, … | each other agent's name | `agents.names` |

These are populated unconditionally; there's no toggle that hides them.
`{opponent2}`, `{opponent3}`, … exist when there are more than two
players. The numbering is positional with respect to the *active* agent.

#### `{intro}: […]` block — always kept, but its inner text is conditional

```
{intro}: [
You are {personality}.
{ownType}: [Your private type is {ownType}; this fact is not visible to {opponent1}.]
]
```

* The outer `{intro}: […]` block survives **unless the agent's
  personality is the literal string `"None"`** — in that case the engine
  strips the whole block so the agent is told nothing about itself.
* `{personality}` is the agent's personality string in the active
  language. Comes from `agents.personalities[lang][i]`.
* The nested `{ownType}: […]` block is **kept only when the
  Configuration assigned a private type to this agent**
  (`agents.types`). Used in Bayesian-game studies. `{ownType}` is the
  realised type label.

#### `{opponentIntro}: […]` — Theory of Mind information

```
{opponentIntro}: [
{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.
{opponent1}'s rolling cooperation rate over recent rounds is {coopRate1}, which we summarise as: {reputation1}.
The prior over types in this population is: {typeDistribution}.
]
```

* The whole block is **stripped at `tomOrder = 0`**. That is the entire
  point of order-0 — the agent is given no information about its
  opponent. At `tomOrder = 1` (default) and `tomOrder = 2`, the block
  survives.
* The block is **also stripped if every opponent has
  `opponentPersonalityProb = 0` or personality `"None"`** — there's
  nothing meaningful to say.
* Inside, the per-opponent placeholders are numbered:
  `{opponent2}` / `{opponentPersonality2}` /
  `{opponentPersonalityProbability2}` / `{coopRate2}` / `{reputation2}`,
  etc.
* `{opponentPersonalityProbability1}` is the probability the opponent
  *truly* has the stated personality, expressed in **0–100**
  (the engine multiplies the 0–1 input by 100 for readability).
* `{coopRate1}` and `{reputation1}` are filled from history:
  - When `reputationApplies = true` and history exists for the opponent,
    `coopRate1` is the fraction (e.g. `"0.62"`) and `reputation1` is one
    of `highly cooperative` / `moderately cooperative` /
    `occasionally cooperative` / `uncooperative`.
  - When `reputationWindow = N`, only the last N rounds are averaged.
  - When `reputationApplies = false` (Battle of the Sexes, zero-sum), or
    there's no history yet, both fields render as `n/a` / `unknown`. Use
    the false case for asymmetric games where strategy1 doesn't mean
    "cooperate".
* `{typeDistribution}` is filled only when the Configuration sets
  `typesAreCommonKnowledge = true` and there's a `agents.types` block;
  otherwise the placeholder will literally appear in the prompt as
  `{typeDistribution}` unless you wrap it in another conditional.
  (See *Edge cases*, §4.3.)

#### `{secondOrder}: […]` — only at `tomOrder = 2`

```
{secondOrder}: [
Be aware: {opponent1} is also reasoning about you, knows that you are reasoning about them, and may try to anticipate your move.
]
```

* Kept iff `tomOrder >= 2`.
* This is where you put any "they-think-we-think" framing. There are no
  new placeholders inside — you compose the recursive reasoning out of
  the same opponent-name placeholders.

#### Cover story (plain text)

```
You and {opponent1} are arrested for a crime and held in separate cells.
```

No conditionals; substitute opponent names if you want, otherwise it's
a frozen narrative. This is also where you control the framing
("crime" → cooperative, "investment" → economic, …) that materially
affects how LLMs respond — it's the most studied source of bias in PD
prompts.

#### Strategies + horizon + round

```
Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds in total.]
The current round is number {currentRound}.
```

* `{strategy1}` / `{strategy2}` / `{strategy3}` … come from the payoff
  matrix's per-language label dict
  (`payoffMatrix.strategies[lang]`). Same logical key, different
  rendering per language — the engine pulls the row matching the active
  language.
* `{gameLength}: […]` survives **only when `nRoundsIsKnown: true`**.
  Removing it lets you study uncertain-horizon behaviour without
  rewriting the body.
* `{currentRound}` is per-round state, 1-indexed.

#### Payoff statement

```
If you both choose {strategy1}, you both get a payoff of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get {weight3} and {opponent1} gets {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get {weight2} and {opponent1} gets {weight3}.
If you both choose {strategy2}, you both get a payoff of {weight4}.
```

* The four `{weightN}` numbers come straight from `payoffMatrix.weights`
  (`weight1`..`weight4` are the engine's standard names for a 2x2). The
  template body is reused across the conventional / harsh / mild
  variants by changing only the weight values.
* Notice the asymmetry: row gets `{weight3}` when row defects-against-
  cooperator, while column gets `{weight2}`. This mirrors the canonical
  PD payoff matrix shape; the matrix tab in the SPA generates this
  symbolically.

#### History

```
This is the history of the choices made so far: {history}.
```

`{history}` is **engine-rendered text** describing past rounds in
human-readable form. There is no template-side control over how it
renders; tweak the engine's history-formatting if you need a different
shape.

#### Phase blocks — exactly ONE survives per prompt render

The engine fires up to three phases per round (communicate → believe →
choose). Each phase fills the prompt template separately with only its
matching `{phase}: [...]` block kept; the other phase blocks are
stripped. That way a single Template handles every phase the engine
might run.

```
{communicate}: [
  ... message-emission instructions ...
]
{choose}: [
  ... pure-strategy choice instructions ...
]
{mixedChoose}: [
  ... probability-distribution instructions ...
]
{believe}: [
  ... belief-elicitation JSON instructions ...
]
```

* `{communicate}: […]` runs once per round before choosing, **only when
  `agentsCommunicate: true`**. The output of this phase becomes the
  message logged into history.
* `{choose}: […]` is the strategy-choice prompt, used when
  `mixedStrategies: false` (default).
* `{mixedChoose}: […]` replaces `{choose}` when `mixedStrategies: true`:
  the LLM returns a JSON probability distribution over strategies and
  the engine samples from it.
* `{believe}: […]` runs once per round before choosing, **only when
  `elicitBeliefs: true`**. The output is parsed as a probability
  distribution and used to compute Brier score later.

You can include all four blocks in a single template; the engine picks
which one to keep at each invocation. If a block isn't present and the
phase fires, the engine will simply send a body with an empty phase
section — usually not what you want, so always include the phase
blocks for every phase your Configuration might enable.

### 4.2 What's NOT yet in this template

A handful of advanced setups need extra markup beyond what's above:

* **More than 2 agents.** Add the equivalent
  `{opponent2}`/`{opponentPersonality2}`/`{opponentPersonalityProbability2}`/
  `{coopRate2}`/`{reputation2}` block (and so on for `{opponent3}`)
  inside `{opponentIntro}: […]`. Same goes for the payoff statement —
  you'll have a row per N-tuple of strategies.
* **More than 2 strategies.** Reference `{strategy3}`, `{strategy4}` …
  in the payoff statement and the phase blocks. The choose and belief
  prompts also need updating to enumerate every strategy.
* **More than 4 weight cells.** Reference `{weight5}`, `{weight6}` …
  for additional weight keys defined in `payoffMatrix.weights`.
* **Stop conditions / continuation probability framing.** These don't
  inject any placeholder by default; if you want the agent to know the
  game might end stochastically, write that into the cover story or
  the `{gameLength}` block manually.
* **Discount factor framing.** Same — the engine applies δ
  numerically; if you want the agent to be told about it, mention it in
  prose.
* **Tournament mode** is a single checkbox at the top of the
  Configurations → Agents tab ("🏆 Run as round-robin tournament"). It
  doesn't change template structure; the engine
  spins up one game per pair and re-uses the same template.
* **Utility transforms** (CRRA, Fehr-Schmidt) are applied on the raw
  payoff *after* the round resolves; the agent sees the raw payoffs in
  the prompt regardless. If you want the transform to be visible to
  the agent, you have to phrase it in prose yourself.

### 4.3 Edge cases / footguns

* **Bare placeholder vs nested block.** A bare `{currentRound}` is
  always substituted. A bare `{ownType}` (no surrounding `{ownType}: […]`
  block) will throw a `KeyError` if no type is configured because the
  engine only injects the value when the surrounding block is kept.
  Always wrap conditional placeholders in their conditional block.
* **Phase blocks must be present.** If your Configuration sets
  `elicitBeliefs: true` but the template has no `{believe}: […]` block,
  the belief-elicitation phase will send an unstructured prompt and
  parsing will fail. The fully-featured template above is the safe
  default; trim only what you're sure you'll never need.
* **`{personality}` outside `{intro}: […]`.** The engine only sets
  `personality` in the placeholder map after the intro block is
  evaluated. A bare `{personality}` outside that block raises
  `KeyError`.
* **Opponent rep before history.** On round 1, `{coopRate1}` is `n/a`.
  Phrase the surrounding sentence so it reads naturally even with
  `n/a` ("rolling rate so far: n/a — no history yet"), or guard it with
  prose ("If history is available, …").
* **Mixed-strategy + believe both on.** Both `{mixedChoose}: […]` and
  `{believe}: […]` will fire. Make sure neither prompt instructs the
  LLM to "output ONLY a single label" in a way that contradicts the
  JSON requirement of the other phase.

---

## 5. The other four canonical games at a glance

| Game | Logical structure | Default payoff weights `(w1, w2, w3, w4)` mapped as `(R, S, T, P)` |
|---|---|---|
| **Stag Hunt** | Coordination — payoff-dominant (Stag, Stag) vs risk-dominant (Hare, Hare). | (4, 1, 0, 2) |
| **Harmony Game** | Mutual cooperation is socially optimal AND strictly dominant. | (5, 2, 4, 1) |
| **Snowdrift** | Anti-coordination — each prefers the other does the work; mutual defection is the worst outcome. | (3, 1, 4, 0) |
| **Battle of the Sexes** | Coordination with two pure equilibria, each favouring one player. | (2, 1, 0, 0) |

Each ships with the same skeleton: identity / opponent intro / cover
story / strategies / `{gameLength}` block / payoff statement / goal /
history / choice prompt. Only the cover story and the goal phrasing
differ — the placeholder structure is identical.

---

## 6. Putting it together — example end-to-end

1. **On the Templates page**, the 5 starter tags are pre-loaded. Open
   "Prisoner's Dilemma" → "classic, en" → click 🌍 **Translate** →
   pick `fr` and `cn` → submit. Two new templates appear under the same
   tag/variation, linked back via `source_template_id`.

2. **On the Configurations page**, click `+ New configuration`:
   * **Name**: "PD harsh, English+French, 5 seeds"
   * **Tag**: Prisoner's Dilemma
   * **Variation**: classic
   * **Languages**: tick `en` (✓) and `fr` (✓ now that you translated).
   * **Basics tab**: set `nRounds = 5`, `nRoundsIsKnown = true`,
     communication = none.
   * **Agents tab** in *per-agent* mode: agent1 = OpenAIGPT4o,
     personality = "cooperative"; agent2 = OpenAIGPT4o, personality =
     "selfish". Or switch to *pool* mode and provide a 3-element
     pool.
   * **Theory of Mind tab**: tomOrder=1, elicitBeliefs=on,
     reputationWindow=3.
   * **Game theory tab**: discountFactor=0.95,
     equilibria=`auto`, baselineSemantics: cooperate→`strategy1`,
     defect→`strategy2`.
   * **Payoff matrix tab**: 4 cells filled with the harsh variant
     payoffs (e.g. (3,3), (-2,5), (5,-2), (-1,-1)).
   * **Reproducibility tab**: seed=42, seedCount=5.
   * Click **💾 Save configuration**.

3. **On the Experiments page**, tick this configuration, set
   "Iterations per config = 3", click **▶ Run experiment**. Three Runs
   land in `results/web/`, one per iteration.

4. **On the Results page**, each run shows: cooperation rate per round
   per agent, score per round, welfare per game, equilibrium rate per
   game, plus the per-game DataFrame.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Configuration must include 'llm' or 'llms'` | The API validator wants a top-level model field. | The SPA injects this automatically from the first agent. If you POSTed JSON manually, add `"llm": "OpenAIGPT4o"` at the top. |
| `No template for tag=… variation=… language=…` | Configuration references languages without a saved template. | On the Templates page, add a template for that (tag, variation, language) — or use 🌍 Translate. |
| `BeliefParseError` repeated | Agent's belief response wasn't valid JSON. | Inspect the raw LLM output in `agentN_messages`. Tighten the template's `{believe}: [...]` block. |
| Live mode but the request 401s | Provider API key not set. | Set `API_KEY_OPENAI` (or Anthropic / Mistral equivalents) in `.env`. |
| Reputation placeholders show "n/a" everywhere | `reputationApplies` is false. | Toggle it on (PD-style games) or leave off (Battle of the Sexes / zero-sum). |

---

## 8. Where things live on disk

```
data/                     # User library (gitignored)
  tags.json
  templates.json
  configurations.json

results/web/              # Run history (gitignored)
  <run_id>/
    metadata.json
    results.csv

resources/config/         # Shipped read-only presets (Python project)
resources/game_templates/ # Default prompt templates (Python project)

fairgame_web.py           # FastAPI + SPA mount
web/index.html            # Vanilla SPA (Tailwind + Alpine via CDN)
src/                      # Engine (factory, payoff matrix, prompt
                          # creator, results processor, …)
```
