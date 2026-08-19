---
id: seed_tpl_gt_stag_conventional_en
game_type_id: gt_stag
variation: conventional
language: en
source_template_id: null
source_language: null
created_at: 2026-01-01T00:00:00
updated_at: 2026-01-01T00:00:00
versions: []
archived: false
---
You are {currentPlayerName} and your hunting partner is {opponent1}.
{intro}: [You are {personality}.]
{opponentIntro}: [{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.]

You and {opponent1} are setting out to hunt. You can each choose to chase a stag together (which only succeeds if you both commit), or to settle for a hare alone (which is guaranteed but worth less).

Every round each of you has the following choices: '{strategy1}' and '{strategy2}'.
{gameLength}: [There are {nRounds} rounds to decide.]
The current round is number {currentRound}.

If you both choose {strategy1} (chase the stag), you each get a reward of {weight1}.
If you choose {strategy1} and {opponent1} chooses {strategy2}, you get a reward of {weight3} and {opponent1} gets a reward of {weight2}.
If you choose {strategy2} and {opponent1} chooses {strategy1}, you get a reward of {weight2} and {opponent1} gets a reward of {weight3}.
If you both choose {strategy2} (catch a hare), you each get a reward of {weight4}.

Your goal is to maximise your reward.
{discount}: [Keep in mind that rewards earned in later rounds matter less to you than rewards earned now, so weight your current and near-term rounds most heavily.]
{riskFrame}: [You are risk-averse: you prefer a smaller but guaranteed reward (such as the hare) over a larger reward that depends on your partner also committing (such as the stag).]
History so far: {history}.
Choose between {strategy1} and {strategy2}.
Output ONLY the choice.
