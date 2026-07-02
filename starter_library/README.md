# FAIRGAME starter library

This folder is the **default content** FAIRGAME ships with: a small, curated set
of games, prompt templates, and ready-to-run configurations. Each configuration
is a distinct experiment, and together they exercise **every feature of the
engine** — so a new user can open the app and immediately run, inspect, and
clone meaningful examples instead of starting from a blank page.

## Layout

The library is **one human-readable file per item**, grouped into three
subfolders. Every filename carries a zero-padded `NN-` prefix so the shipped
order is preserved and obvious at a glance.

| Folder | What it holds | Format |
| --- | --- | --- |
| `game_types/` | The games (7): Prisoner's Dilemma, Stag Hunt, Snow Drift, Harmony Game, Battle of the Sexes, Volunteer's Dilemma, Zero-sum | one pretty-printed `.json` per game |
| `templates/` | Prompt templates (14) — per game/variant/language | one `.md` per template: YAML frontmatter (metadata) + the raw, un-escaped prompt body |
| `configurations/` | Runnable configurations (20) — the experiments below | one pretty-printed `.json` per configuration |
| `README.md` | This file | — |

A template file looks like:

```markdown
---
id: seed_tpl_gt_pd_conventional_en
game_type_id: gt_pd
variation: conventional
language: en
---
You are {currentPlayerName} and your opponent is {opponent1}.
...the prompt body, exactly as sent to the model...
```

## How it's loaded

`web_api/seeds.py` reads every file in these subfolders (in filename order) and
exposes them as `SEED_GAME_TYPES`, `SEED_TEMPLATES`, and `SEED_CONFIGURATIONS`.
For templates it parses the frontmatter into the record metadata and keeps the
text below the closing `---` as the `body`. On a fresh install the storage layer
(`web_api/storage.py`) seeds the on-disk store from these on first use and tops
up any missing entries. Edit the files here to change what ships — add a new
file (mind the `NN-` prefix for ordering) to add an item, or delete one to drop
it.

To regenerate the whole folder from the canonical presets, run
`python tools/build_seed_library.py` (it rewrites every file and prunes any that
no longer correspond to a preset).

## The 20 starter experiments

| Configuration | Game | Features demonstrated |
| --- | --- | --- |
| PD — baseline round-robin tournament (offline) | Prisoner's Dilemma | baseline, tournament, personality pool, stop conditions |
| PD — LLM head-to-head | Prisoner's Dilemma | personality pool, stop conditions |
| PD — real communication | Prisoner's Dilemma | real communication, personality pool, stop conditions |
| PD — covert signalling (hex decoy) | Prisoner's Dilemma | covert/decoy messages, personality pool, stop conditions |
| PD — theory of mind + beliefs | Prisoner's Dilemma | belief elicitation, theory-of-mind order 2, personality pool, stop conditions |
| PD — mixed strategies (multi-seed + equilibria) | Prisoner's Dilemma | mixed strategies, multi-seed averaging, equilibrium scoring, personality pool, stop conditions |
| PD — trust / costly monitoring | Prisoner's Dilemma | personality pool, trust / costly monitoring, stop conditions |
| PD — inequity aversion (Fehr-Schmidt) | Prisoner's Dilemma | Fehr-Schmidt inequity aversion, personality pool, stop conditions |
| PD — risk aversion + discounting | Prisoner's Dilemma | CRRA risk aversion, time discounting, personality pool, stop conditions |
| PD — personality pool permutations | Prisoner's Dilemma | personality pool, stop conditions |
| PD — multilingual (EN + FR) | Prisoner's Dilemma | personality pool, multilingual, stop conditions |
| PD — payoff sweep (mild vs harsh) | Prisoner's Dilemma | payoff sweep (group), personality pool, stop conditions |
| PD — uncertain horizon | Prisoner's Dilemma | uncertain horizon, personality pool |
| Stag Hunt — coordination | Stag Hunt | equilibrium scoring, personality pool |
| Snow Drift — anti-coordination | Snow Drift | equilibrium scoring, personality pool |
| Harmony Game — dominant cooperation | Harmony Game | equilibrium scoring, personality pool |
| Battle of the Sexes — multilingual (EN+FR) | Battle of the Sexes | personality pool, multilingual, reputation off |
| Volunteer's Dilemma — n-player | Volunteer's Dilemma | stop conditions |
| Zero-sum — strictly competitive | Zero-sum | personality pool, reputation off |
| PD — interaction graph (asymmetric visibility) | Prisoner's Dilemma | interaction graph (directed visibility + one-way messaging), real communication |

## Coverage

Across these configurations the library exercises: baseline strategies,
round-robin tournaments, real and covert/decoy communication, theory-of-mind and
belief elicitation, mixed strategies, multi-seed averaging, equilibrium scoring,
CRRA risk aversion, Fehr-Schmidt inequity aversion, time discounting, uncertain
horizons, personality pools, trust/costly monitoring, multilingual runs, payoff
sweeps (configuration groups), stop conditions, reputation-off games, and
n-player and zero-sum games — across 7 classic game families.
