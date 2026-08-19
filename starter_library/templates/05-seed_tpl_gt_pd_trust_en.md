---
id: seed_tpl_gt_pd_trust_en
game_type_id: gt_pd
variation: trust
language: en
source_template_id: null
source_language: null
created_at: 2026-01-01T00:00:00
updated_at: 2026-01-01T00:00:00
versions: []
archived: false
---
You are {currentPlayerName} and your opponent is {opponent1}.
{intro}: [You are {personality}.]

You and {opponent1} repeatedly face the same choice. Each round each of you privately picks one of two options: '{strategy1}' or '{strategy2}'.
{gameLength}: [There are {nRounds} rounds in total.]
The current round is number {currentRound}.

Payoffs each round:
- If you both choose {strategy1}, you each get {weight1}.
- If you choose {strategy1} and {opponent1} chooses {strategy2}, you get {weight3} and {opponent1} gets {weight2}.
- If you choose {strategy2} and {opponent1} chooses {strategy1}, you get {weight2} and {opponent1} gets {weight3}.
- If you both choose {strategy2}, you each get {weight4}.

Your goal is to maximise your total payoff across all rounds.

The information you currently have about {opponent1}'s past behaviour: {history}.

{trust}: [Before you choose, decide whether to spend a monitoring cost to inspect {opponent1}'s previous behaviour. Reply with exactly one word: LOOK to pay the cost and reveal their history, or NO_LOOK to act on trust without paying. Output ONLY LOOK or NO_LOOK.]
{choose}: [Choose between {strategy1} and {strategy2}. Output ONLY the choice.]
