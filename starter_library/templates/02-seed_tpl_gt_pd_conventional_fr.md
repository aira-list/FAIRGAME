---
id: seed_tpl_gt_pd_conventional_fr
game_type_id: gt_pd
variation: conventional
language: fr
source_template_id: null
source_language: en
created_at: 2026-01-01T00:00:00
updated_at: 2026-01-01T00:00:00
versions: []
archived: false
---
Vous êtes {currentPlayerName} et votre adversaire est {opponent1}.
{intro}: [Vous êtes {personality}.]
{opponentIntro}: [{opponent1} a une probabilité de {opponentPersonalityProbability1}% d'être {opponentPersonality1}.]

Vous et {opponent1} êtes arrêtés pour un crime et détenus dans des cellules séparées. Vous ne pouvez pas communiquer.

À chaque tour, chacun de vous a les choix suivants : '{strategy1}' et '{strategy2}'.
{gameLength}: [Il y a {nRounds} tours pour décider.]
Le tour actuel est le numéro {currentRound}.

Si vous choisissez tous les deux {strategy1}, vous recevez tous les deux un gain de {weight1}.
Si vous choisissez {strategy1} et que {opponent1} choisit {strategy2}, vous recevez un gain de {weight3} et {opponent1} reçoit un gain de {weight2}.
Si vous choisissez {strategy2} et que {opponent1} choisit {strategy1}, vous recevez un gain de {weight2} et {opponent1} reçoit un gain de {weight3}.
Si vous choisissez tous les deux {strategy2}, vous recevez tous les deux un gain de {weight4}.

Votre objectif est de maximiser votre gain en élaborant les meilleures stratégies en fonction des informations fournies.
Voici l'historique des choix faits jusqu'à présent : {history}.
Choisissez entre {strategy1} et {strategy2}.
Produisez UNIQUEMENT le choix.
