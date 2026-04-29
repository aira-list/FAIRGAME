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

## 4. Walkthrough: the 5 canonical templates

The library auto-seeds with the five 2x2 games. Each `body` follows the
same skeleton. Let's annotate the **Prisoner's Dilemma** template
line-by-line.

### 4.1 Prisoner's Dilemma — the annotated template

```
You are {currentPlayerName} and your opponent is {opponent1}.
{intro}: [You are {personality}.]
{opponentIntro}: [{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.]
```

* **Line 1** — bare names. `{currentPlayerName}` is the agent's own
  name (one of `agents.names`). `{opponent1}` is the first other agent.
* **Line 2** — `{intro}: [...]` is always kept. Inside the brackets,
  `{personality}` is the agent's personality string for the active
  language.
* **Line 3** — `{opponentIntro}: [...]` is **stripped at tomOrder=0**, so
  in 0-th order ToM the agent is told nothing about the opponent.
  `{opponentPersonality1}` and `{opponentPersonalityProbability1}` are
  injected together so the prompt can hedge ("60% likely to be selfish").

```
You and {opponent1} are arrested for a crime and held in separate cells. You cannot communicate.
```

* The cover story. Plain text — no placeholders.

```
Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.
```

* `{strategy1}` / `{strategy2}` come from the payoff matrix
  (`payoffMatrix.strategies[lang]`). Different languages → different
  display labels but the same logical strategy keys.
* `{gameLength}: [...]` is **kept only when `nRoundsIsKnown: true`**.
  This lets you flip whether the agent knows the horizon by toggling a
  single Configuration field.
* `{currentRound}` is per-round state.

```
If you both choose {strategy1}, you both get a penalty of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a penalty of {weight3} and {opponent1} gets a penalty of {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a penalty of {weight2} and {opponent1} gets a penalty of {weight3}.
If you both choose {strategy2}, you both get a penalty of {weight4}.
```

* The full payoff statement. The four `{weightN}` references map to
  `payoffMatrix.weights`. By naming weights instead of inlining numbers,
  the same template body is reused across the "conventional" / "harsh"
  / "mild" PD variants — only the weight values change.

```
Your goal is to minimize your penalty by making the best strategies based on the provided information.
This is the history of the choices made so far: {history}.
Choose between {strategy1} and {strategy2}.
Output ONLY the choice.
```

* `{history}` is engine-rendered text describing past rounds.
* `Output ONLY the choice.` is the format constraint that the engine's
  belief / strategy parser expects.

### 4.2 The other four games at a glance

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

## 5. Putting it together — example end-to-end

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

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Configuration must include 'llm' or 'llms'` | The API validator wants a top-level model field. | The SPA injects this automatically from the first agent. If you POSTed JSON manually, add `"llm": "OpenAIGPT4o"` at the top. |
| `No template for tag=… variation=… language=…` | Configuration references languages without a saved template. | On the Templates page, add a template for that (tag, variation, language) — or use 🌍 Translate. |
| `BeliefParseError` repeated | Agent's belief response wasn't valid JSON. | Inspect the raw LLM output in `agentN_messages`. Tighten the template's `{believe}: [...]` block. |
| Live mode but the request 401s | Provider API key not set. | Set `API_KEY_OPENAI` (or Anthropic / Mistral equivalents) in `.env`. |
| Reputation placeholders show "n/a" everywhere | `reputationApplies` is false. | Toggle it on (PD-style games) or leave off (Battle of the Sexes / zero-sum). |

---

## 7. Where things live on disk

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
