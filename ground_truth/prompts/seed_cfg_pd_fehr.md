# Ground-truth prompts — PD — inequity aversion (Fehr-Schmidt)

- **config id:** `seed_cfg_pd_fehr`
- **game_type:** `gt_pd`  •  **variation:** `conventional`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 8 total, 4 unique

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
