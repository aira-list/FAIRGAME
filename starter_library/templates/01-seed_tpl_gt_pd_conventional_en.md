---
id: seed_tpl_gt_pd_conventional_en
game_type_id: gt_pd
variation: conventional
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

You and {opponent1} are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds to decide.] 
The current round is number {currentRound}.
    
If you both choose {strategy1}, you both get a payoff of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a payoff of {weight3} and {opponent1} gets a payoff of {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a payoff of {weight2} and {opponent1} gets a payoff of {weight3}.
If you both choose {strategy2}, you both get a payoff of {weight4}.

Your goal is to maximise your payoff by making the best strategies based on the provided information.
{discount}: [Keep in mind that payoffs earned in later rounds matter less to you than payoffs earned now, so weight your current and near-term rounds most heavily.]
{riskFrame}: [You are risk-averse: you prefer an outcome that is more certain over a gamble with the same or even slightly better expected payoff.]
This is the history of the choices made so far: {history}.
Choose between {strategy1} and {strategy2}.
Output ONLY the choice.