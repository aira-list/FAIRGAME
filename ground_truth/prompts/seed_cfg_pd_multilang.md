# Ground-truth prompts — PD — multilingual (EN + FR)

- **config id:** `seed_cfg_pd_multilang`
- **game_type:** `gt_pd`  •  **variation:** `conventional`  •  **languages:** ['en', 'fr']
- **run status:** ok
- **prompts sent:** 16 total, 8 unique

## 1. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2. 
You are cooperative.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide. 
The current round is number 1.
    
If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty by making the best strategies based on the provided information.


This is the history of the choices made so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.
```

## 2. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1. 
You are cooperative.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide. 
The current round is number 1.
    
If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty by making the best strategies based on the provided information.


This is the history of the choices made so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.
```

## 3. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1. 
You are selfish.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide. 
The current round is number 1.
    
If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty by making the best strategies based on the provided information.


This is the history of the choices made so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.
```

## 4. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2. 
You are selfish.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide. 
The current round is number 1.
    
If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty by making the best strategies based on the provided information.


This is the history of the choices made so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.
```

## 5. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
```
Vous êtes agent1 et votre adversaire est agent2.
Vous êtes coopératif.


Vous et agent2 êtes arrêtés pour un crime et détenus dans des cellules séparées. Vous ne pouvez pas communiquer.

À chaque tour, chacun de vous a les choix suivants : 'OptionA' et 'OptionB'.
Il y a 1 tours pour décider.
Le tour actuel est le numéro 1.

Si vous choisissez tous les deux OptionA, vous recevez tous les deux une pénalité de 6.
Si vous choisissez OptionA et que agent2 choisit OptionB, vous recevez une pénalité de 0 et agent2 reçoit une pénalité de 10.
Si vous choisissez OptionB et que agent2 choisit OptionA, vous recevez une pénalité de 10 et agent2 reçoit une pénalité de 0.
Si vous choisissez tous les deux OptionB, vous recevez tous les deux une pénalité de 2.

Votre objectif est de minimiser votre pénalité en élaborant les meilleures stratégies en fonction des informations fournies.
Voici l'historique des choix faits jusqu'à présent : {}.
Choisissez entre OptionA et OptionB.
Produisez UNIQUEMENT le choix.
```
```

## 6. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
```
Vous êtes agent2 et votre adversaire est agent1.
Vous êtes coopératif.


Vous et agent1 êtes arrêtés pour un crime et détenus dans des cellules séparées. Vous ne pouvez pas communiquer.

À chaque tour, chacun de vous a les choix suivants : 'OptionA' et 'OptionB'.
Il y a 1 tours pour décider.
Le tour actuel est le numéro 1.

Si vous choisissez tous les deux OptionA, vous recevez tous les deux une pénalité de 6.
Si vous choisissez OptionA et que agent1 choisit OptionB, vous recevez une pénalité de 0 et agent1 reçoit une pénalité de 10.
Si vous choisissez OptionB et que agent1 choisit OptionA, vous recevez une pénalité de 10 et agent1 reçoit une pénalité de 0.
Si vous choisissez tous les deux OptionB, vous recevez tous les deux une pénalité de 2.

Votre objectif est de minimiser votre pénalité en élaborant les meilleures stratégies en fonction des informations fournies.
Voici l'historique des choix faits jusqu'à présent : {}.
Choisissez entre OptionA et OptionB.
Produisez UNIQUEMENT le choix.
```
```

## 7. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
```
Vous êtes agent2 et votre adversaire est agent1.
Vous êtes égoïste.


Vous et agent1 êtes arrêtés pour un crime et détenus dans des cellules séparées. Vous ne pouvez pas communiquer.

À chaque tour, chacun de vous a les choix suivants : 'OptionA' et 'OptionB'.
Il y a 1 tours pour décider.
Le tour actuel est le numéro 1.

Si vous choisissez tous les deux OptionA, vous recevez tous les deux une pénalité de 6.
Si vous choisissez OptionA et que agent1 choisit OptionB, vous recevez une pénalité de 0 et agent1 reçoit une pénalité de 10.
Si vous choisissez OptionB et que agent1 choisit OptionA, vous recevez une pénalité de 10 et agent1 reçoit une pénalité de 0.
Si vous choisissez tous les deux OptionB, vous recevez tous les deux une pénalité de 2.

Votre objectif est de minimiser votre pénalité en élaborant les meilleures stratégies en fonction des informations fournies.
Voici l'historique des choix faits jusqu'à présent : {}.
Choisissez entre OptionA et OptionB.
Produisez UNIQUEMENT le choix.
```
```

## 8. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
```
Vous êtes agent1 et votre adversaire est agent2.
Vous êtes égoïste.


Vous et agent2 êtes arrêtés pour un crime et détenus dans des cellules séparées. Vous ne pouvez pas communiquer.

À chaque tour, chacun de vous a les choix suivants : 'OptionA' et 'OptionB'.
Il y a 1 tours pour décider.
Le tour actuel est le numéro 1.

Si vous choisissez tous les deux OptionA, vous recevez tous les deux une pénalité de 6.
Si vous choisissez OptionA et que agent2 choisit OptionB, vous recevez une pénalité de 0 et agent2 reçoit une pénalité de 10.
Si vous choisissez OptionB et que agent2 choisit OptionA, vous recevez une pénalité de 10 et agent2 reçoit une pénalité de 0.
Si vous choisissez tous les deux OptionB, vous recevez tous les deux une pénalité de 2.

Votre objectif est de minimiser votre pénalité en élaborant les meilleures stratégies en fonction des informations fournies.
Voici l'historique des choix faits jusqu'à présent : {}.
Choisissez entre OptionA et OptionB.
Produisez UNIQUEMENT le choix.
```
```
