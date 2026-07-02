---
id: seed_tpl_gt_pd_mixed_en
game_type_id: gt_pd
variation: mixed
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

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.

If you both choose {strategy1}, you both get a penalty of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a penalty of {weight3} and {opponent1} gets a penalty of {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a penalty of {weight2} and {opponent1} gets a penalty of {weight3}.
If you both choose {strategy2}, you both get a penalty of {weight4}.

History so far: {history}.

{mixedChoose}: [Output your strategy as a JSON probability distribution like predict the opponent: {{"{strategy1}": 0.6, "{strategy2}": 0.4}}. Output ONLY the JSON.]
