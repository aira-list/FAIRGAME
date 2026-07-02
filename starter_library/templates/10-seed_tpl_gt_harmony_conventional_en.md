---
id: seed_tpl_gt_harmony_conventional_en
game_type_id: gt_harmony
variation: conventional
language: en
source_template_id: null
source_language: null
created_at: 2026-01-01T00:00:00
updated_at: 2026-01-01T00:00:00
versions: []
archived: false
---
You are {currentPlayerName} and the other player is {opponent1}.
{intro}: [You are {personality}.]
{opponentIntro}: [{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.]

You and {opponent1} are working on a shared project. Cooperation strictly dominates: each of you is better off cooperating regardless of what the other does.

Every round each of you has the following choices: '{strategy1}' (cooperate) and '{strategy2}' (defect).

{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.

If you both choose {strategy1}, you each get a reward of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a reward of {weight2} and {opponent1} gets a reward of {weight3}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a reward of {weight3} and {opponent1} gets a reward of {weight2}.
If you both choose {strategy2}, you each get a reward of {weight4}.

Your goal is to maximise your reward.
History so far: {history}.
Choose between {strategy1} and {strategy2}.
Output ONLY the choice.
