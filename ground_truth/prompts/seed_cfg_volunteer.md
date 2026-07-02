# Ground-truth prompts — Volunteer's Dilemma — n-player

- **config id:** `seed_cfg_volunteer`
- **game_type:** `gt_volunteer`  •  **variation:** `conventional`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 3 total, 3 unique

## 1. phase=`choose`  agent=`agent1`  model=`GPT-4o`

```text
You are agent1. Your opponents are agent2 and agent3.
You are cooperative.


The three of you are in a critical situation. If at least one person volunteers, the group is safe—but the volunteer pays a cost. If no one volunteers, everyone suffers a much heavier penalty. You cannot coordinate your choices. Each of you must act independently, but the outcome affects everyone.

Each round, all three players choose between 'OptionA' (volunteer) and 'OptionB' (do nothing).
There are 10 rounds to decide.
The current round is 1.

The outcomes are as follows:
– If at least one person chooses OptionA, those who chose OptionA receive a penalty of 0, and those who chose OptionB receive no penalty.
– If no one chooses OptionA, all players receive a penalty of 5.

Your goal is to maximize your personal outcome (minimize your penalty), while considering the personalities and potential strategies of the other two players.

This is the history of the choices made so far: {}.

Choose between OptionA and OptionB. Output ONLY the choice.


```

## 2. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`

```text
You are agent2. Your opponents are agent1 and agent3.
You are aggressive.


The three of you are in a critical situation. If at least one person volunteers, the group is safe—but the volunteer pays a cost. If no one volunteers, everyone suffers a much heavier penalty. You cannot coordinate your choices. Each of you must act independently, but the outcome affects everyone.

Each round, all three players choose between 'OptionA' (volunteer) and 'OptionB' (do nothing).
There are 10 rounds to decide.
The current round is 1.

The outcomes are as follows:
– If at least one person chooses OptionA, those who chose OptionA receive a penalty of 0, and those who chose OptionB receive no penalty.
– If no one chooses OptionA, all players receive a penalty of 5.

Your goal is to maximize your personal outcome (minimize your penalty), while considering the personalities and potential strategies of the other two players.

This is the history of the choices made so far: {}.

Choose between OptionA and OptionB. Output ONLY the choice.


```

## 3. phase=`choose`  agent=`agent3`  model=`GPT-4o`

```text
You are agent3. Your opponents are agent1 and agent2.
You are agressive.


The three of you are in a critical situation. If at least one person volunteers, the group is safe—but the volunteer pays a cost. If no one volunteers, everyone suffers a much heavier penalty. You cannot coordinate your choices. Each of you must act independently, but the outcome affects everyone.

Each round, all three players choose between 'OptionA' (volunteer) and 'OptionB' (do nothing).
There are 10 rounds to decide.
The current round is 1.

The outcomes are as follows:
– If at least one person chooses OptionA, those who chose OptionA receive a penalty of 0, and those who chose OptionB receive no penalty.
– If no one chooses OptionA, all players receive a penalty of 5.

Your goal is to maximize your personal outcome (minimize your penalty), while considering the personalities and potential strategies of the other two players.

This is the history of the choices made so far: {}.

Choose between OptionA and OptionB. Output ONLY the choice.


```
