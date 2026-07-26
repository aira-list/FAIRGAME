---
id: seed_tpl_gt_zerosum_conventional_en
game_type_id: gt_zerosum
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

You and {opponent1} are playing a strictly zero-sum matching game: whatever one of you wins, the other loses. The unique equilibrium is in mixed strategies.

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.

{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.

If you both choose the same option, agent1 gets a reward of {weight1} and agent2 gets a reward of {weight2}.
If you choose different options, agent1 gets a reward of {weight2} and agent2 gets a reward of {weight1}.
One of you wins exactly what the other loses: agent1 wants to match, agent2 wants to mismatch.

Your goal is to maximise your reward.
History so far: {history}.
Choose between {strategy1} and {strategy2}.
Output ONLY the choice.
