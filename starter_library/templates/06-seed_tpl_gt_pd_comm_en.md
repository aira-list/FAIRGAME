---
id: seed_tpl_gt_pd_comm_en
game_type_id: gt_pd
variation: comm
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
{opponentIntro}: [{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.]

You and {opponent1} repeatedly face the same choice. Before each round you may exchange one short message with {opponent1}, then you both choose privately and simultaneously.

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.

If you both choose {strategy1}, you both get a payoff of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a payoff of {weight3} and {opponent1} gets a payoff of {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a payoff of {weight2} and {opponent1} gets a payoff of {weight3}.
If you both choose {strategy2}, you both get a payoff of {weight4}.

Your goal is to maximize your payoff by making the best choices based on the provided information.
This is the history of the choices made and messages exchanged so far: {history}.
{communicate}: [Send one short message to {opponent1} before this round's choice. It is up to you whether to coordinate, persuade, bluff, or stay silent. Output ONLY the message text, at most one sentence.]
{choose}: [Choose between {strategy1} and {strategy2}. Output ONLY the choice.]
