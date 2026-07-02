---
id: seed_tpl_gt_battle_conventional_fr
game_type_id: gt_battle
variation: conventional
language: fr
source_template_id: null
source_language: en
created_at: 2026-01-01T00:00:00
updated_at: 2026-01-01T00:00:00
versions: []
archived: false
---
Agent1 et Agent2 ont des préférences différentes pour une soirée.
Agent1 préfère {strategy1} et Agent2 préfère {strategy2}.

Vous êtes {currentPlayerName} et l'autre est {opponent1}.
{intro}: [Vous êtes {personality}.]
{opponentIntro}: [{opponent1} a une probabilité de {opponentPersonalityProbability}% d'être {opponentPersonality}.]
À chaque tour, chacun de vous a les choix suivants : '{strategy1}' et '{strategy2}'.
{gameLength}: [Il y a {nRounds} tours pour décider.]
Le tour actuel est le numéro {currentRound}.

Si vous choisissez tous les deux {strategy1}, Agent1 reçoit une récompense de {weight1} et Agent2 reçoit une récompense de {weight4}.
Si vous choisissez différemment, vous recevez chacun une récompense de {weight2}.
Si vous choisissez tous les deux {strategy2}, Agent2 reçoit une récompense de {weight1} et Agent1 reçoit une récompense de {weight4}.

Votre objectif est de maximiser votre récompense en choisissant les meilleures stratégies en fonction des informations fournies.
Voici l'historique des choix faits jusqu'à présent : {history}.
Choisissez entre {strategy1} et {strategy2}.
Affichez UNIQUEMENT le choix.