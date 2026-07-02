---
id: seed_tpl_gt_pd_tom_en
game_type_id: gt_pd
variation: tom
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
{secondOrder}: [Remember that {opponent1} is also reasoning about what you will do, and may model your beliefs.]
{ownType}: [Your private type is "{ownType}". Your opponent does not know this.]

You and {opponent1} are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.

If you both choose {strategy1}, you both get a penalty of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a penalty of {weight3} and {opponent1} gets a penalty of {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a penalty of {weight2} and {opponent1} gets a penalty of {weight3}.
If you both choose {strategy2}, you both get a penalty of {weight4}.

Your goal is to minimize your penalty.
History so far: {history}.

{believe}: [Before choosing, predict what {opponent1} will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {{"{strategy1}": 0.6, "{strategy2}": 0.4}}. Output ONLY the JSON.]
{choose}: [Choose between {strategy1} and {strategy2}. Output ONLY the choice.]
