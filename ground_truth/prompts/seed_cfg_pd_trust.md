# Ground-truth prompts — PD — trust / costly monitoring

- **config id:** `seed_cfg_pd_trust`
- **game_type:** `gt_pd`  •  **variation:** `trust`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 16 total, 8 unique

## 1. phase=`trust`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2.
You are cooperative.

You and agent2 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent2 chooses OptionB, you get 10 and agent2 gets 0.
- If you choose OptionB and agent2 chooses OptionA, you get 0 and agent2 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent2's past behaviour: {}.

Before you choose, decide whether to spend a monitoring cost to inspect agent2's previous behaviour. Reply with exactly one word: LOOK to pay the cost and reveal their history, or NO_LOOK to act on trust without paying. Output ONLY LOOK or NO_LOOK.


```

## 2. phase=`trust`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1.
You are cooperative.

You and agent1 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent1 chooses OptionB, you get 10 and agent1 gets 0.
- If you choose OptionB and agent1 chooses OptionA, you get 0 and agent1 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent1's past behaviour: {}.

Before you choose, decide whether to spend a monitoring cost to inspect agent1's previous behaviour. Reply with exactly one word: LOOK to pay the cost and reveal their history, or NO_LOOK to act on trust without paying. Output ONLY LOOK or NO_LOOK.


```

## 3. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2.
You are cooperative.

You and agent2 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent2 chooses OptionB, you get 10 and agent2 gets 0.
- If you choose OptionB and agent2 chooses OptionA, you get 0 and agent2 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent2's past behaviour: {}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 4. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1.
You are cooperative.

You and agent1 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent1 chooses OptionB, you get 10 and agent1 gets 0.
- If you choose OptionB and agent1 chooses OptionA, you get 0 and agent1 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent1's past behaviour: {}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 5. phase=`trust`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1.
You are selfish.

You and agent1 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent1 chooses OptionB, you get 10 and agent1 gets 0.
- If you choose OptionB and agent1 chooses OptionA, you get 0 and agent1 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent1's past behaviour: {}.

Before you choose, decide whether to spend a monitoring cost to inspect agent1's previous behaviour. Reply with exactly one word: LOOK to pay the cost and reveal their history, or NO_LOOK to act on trust without paying. Output ONLY LOOK or NO_LOOK.


```

## 6. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1.
You are selfish.

You and agent1 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent1 chooses OptionB, you get 10 and agent1 gets 0.
- If you choose OptionB and agent1 chooses OptionA, you get 0 and agent1 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent1's past behaviour: {}.


Choose between OptionA and OptionB. Output ONLY the choice.

```

## 7. phase=`trust`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2.
You are selfish.

You and agent2 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent2 chooses OptionB, you get 10 and agent2 gets 0.
- If you choose OptionB and agent2 chooses OptionA, you get 0 and agent2 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent2's past behaviour: {}.

Before you choose, decide whether to spend a monitoring cost to inspect agent2's previous behaviour. Reply with exactly one word: LOOK to pay the cost and reveal their history, or NO_LOOK to act on trust without paying. Output ONLY LOOK or NO_LOOK.


```

## 8. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2.
You are selfish.

You and agent2 repeatedly face the same choice. Each round each of you privately picks one of two options: 'OptionA' or 'OptionB'.
There are 1 rounds in total.
The current round is number 1.

Payoffs each round:
- If you both choose OptionA, you each get 6.
- If you choose OptionA and agent2 chooses OptionB, you get 10 and agent2 gets 0.
- If you choose OptionB and agent2 chooses OptionA, you get 0 and agent2 gets 10.
- If you both choose OptionB, you each get 2.

The information you currently have about agent2's past behaviour: {}.


Choose between OptionA and OptionB. Output ONLY the choice.

```
