---
id: seed_tpl_gt_volunteer_conventional_en
game_type_id: gt_volunteer
variation: conventional
language: en
source_template_id: null
source_language: null
created_at: 2026-01-01T00:00:00
updated_at: 2026-01-01T00:00:00
versions: []
archived: false
---
You are {currentPlayerName}. Your opponents are {opponent1} and {opponent2}.
{intro}: [You are {personality}.]
{opponentIntro}: [{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}, {opponent2} has a probability of {opponentPersonalityProbability2}% of being {opponentPersonality2}.]

The three of you are in a critical situation. If at least one person volunteers, the group is safe—but the volunteer pays a cost. If no one volunteers, everyone ends up with the worst outcome. You cannot coordinate your choices. Each of you must act independently, but the outcome affects everyone.

Each round, all three players choose between '{strategy1}' (do nothing) and '{strategy2}' (volunteer).
{gameLength}: [There are {nRounds} rounds to decide.]
The current round is {currentRound}.

The outcomes are as follows:
– If at least one person chooses {strategy2}, each person who chose {strategy2} receives a payoff of {weight2} (the benefit minus the volunteer's cost), and each person who chose {strategy1} receives a payoff of {weight3} (the full benefit).
– If no one chooses {strategy2}, all players receive a payoff of {weight1}.

Your goal is to maximize your personal payoff, while considering the personalities and potential strategies of the other two players.

This is the history of the choices made so far: {history}.
{communicate}: [You can now send a message to both opponents. Stay fully in character. Speak as if this were a real situation with real consequences. Do not break the scenario or refer to it as a game. Be persuasive, strategic, and believable. Output only the message you would send.]
{choose}: [Choose between {strategy1} and {strategy2}. Output ONLY the choice.]

