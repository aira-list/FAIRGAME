# Ground-truth prompts — PD — theory of mind + beliefs

- **config id:** `seed_cfg_pd_tom`
- **game_type:** `gt_pd`  •  **variation:** `tom`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 128 total, 16 unique

## 1. phase=`belief/mixed`  agent=`agent1`  model=`GPT-4o`  ×12

```text
You are agent1 and your opponent is agent2.
You are cooperative.
agent2 has a probability of 0.7% of being cooperative.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {}.

Before choosing, predict what agent2 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 2. phase=`belief/mixed`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×12

```text
You are agent2 and your opponent is agent1.
You are cooperative.
agent1 has a probability of 0.7% of being cooperative.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}}}.

Before choosing, predict what agent1 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 3. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×4

```text
You are agent1 and your opponent is agent2.
You are cooperative.
agent2 has a probability of 0.7% of being cooperative.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 4. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×4

```text
You are agent2 and your opponent is agent1.
You are cooperative.
agent1 has a probability of 0.7% of being cooperative.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 5. phase=`belief/mixed`  agent=`agent1`  model=`GPT-4o`  ×12

```text
You are agent1 and your opponent is agent2.
You are cooperative.
agent2 has a probability of 0.7% of being selfish.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {}.

Before choosing, predict what agent2 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 6. phase=`belief/mixed`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×12

```text
You are agent2 and your opponent is agent1.
You are selfish.
agent1 has a probability of 0.7% of being cooperative.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}}}.

Before choosing, predict what agent1 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 7. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×4

```text
You are agent1 and your opponent is agent2.
You are cooperative.
agent2 has a probability of 0.7% of being selfish.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 8. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×4

```text
You are agent2 and your opponent is agent1.
You are selfish.
agent1 has a probability of 0.7% of being cooperative.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 9. phase=`belief/mixed`  agent=`agent1`  model=`GPT-4o`  ×12

```text
You are agent1 and your opponent is agent2.
You are selfish.
agent2 has a probability of 0.7% of being cooperative.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {}.

Before choosing, predict what agent2 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 10. phase=`belief/mixed`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×12

```text
You are agent2 and your opponent is agent1.
You are cooperative.
agent1 has a probability of 0.7% of being selfish.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}}}.

Before choosing, predict what agent1 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 11. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×4

```text
You are agent1 and your opponent is agent2.
You are selfish.
agent2 has a probability of 0.7% of being cooperative.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 12. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×4

```text
You are agent2 and your opponent is agent1.
You are cooperative.
agent1 has a probability of 0.7% of being selfish.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 13. phase=`belief/mixed`  agent=`agent1`  model=`GPT-4o`  ×12

```text
You are agent1 and your opponent is agent2.
You are selfish.
agent2 has a probability of 0.7% of being selfish.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {}.

Before choosing, predict what agent2 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 14. phase=`belief/mixed`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×12

```text
You are agent2 and your opponent is agent1.
You are selfish.
agent1 has a probability of 0.7% of being selfish.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}}}.

Before choosing, predict what agent1 will do this round. Reply ONLY with a JSON object mapping each strategy label to a probability that sums to 1, e.g. {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.


```

## 15. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×4

```text
You are agent1 and your opponent is agent2.
You are selfish.
agent2 has a probability of 0.7% of being selfish.
Remember that agent2 is also reasoning about what you will do, and may model your beliefs.


You and agent2 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 16. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×4

```text
You are agent2 and your opponent is agent1.
You are selfish.
agent1 has a probability of 0.7% of being selfish.
Remember that agent1 is also reasoning about what you will do, and may model your beliefs.


You and agent1 are arrested for a crime and held in separate cells. You cannot communicate.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent1 chooses OptionB, you get a penalty of 0 and agent1 gets a penalty of 10.
If you choose OptionB and agent1 chooses OptionA, you get a penalty of 10 and agent1 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

Your goal is to minimize your penalty.
History so far: {'round_1': {'agent1': {'belief': None}, 'agent2': {'belief': None}}}.


Choose between OptionA and OptionB. Output ONLY the choice.

```
