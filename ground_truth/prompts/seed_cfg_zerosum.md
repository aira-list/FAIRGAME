# Ground-truth prompts — Zero-sum — strictly competitive

- **config id:** `seed_cfg_zerosum`
- **game_type:** `gt_zerosum`  •  **variation:** `conventional`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 8 total, 4 unique

## 1. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2.
You are cooperative.


You and agent2 are playing a strictly zero-sum matching game: whatever one of you wins, the other loses. The unique equilibrium is in mixed strategies.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.

There are 1 rounds to decide.
The current round is number 1.

If you both choose the same option, you get a reward of 2 and agent2 gets a reward of -2.
If you choose differently, you get a reward of -2 and agent2 gets a reward of 2.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 2. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1.
You are cooperative.


You and agent1 are playing a strictly zero-sum matching game: whatever one of you wins, the other loses. The unique equilibrium is in mixed strategies.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.

There are 1 rounds to decide.
The current round is number 1.

If you both choose the same option, you get a reward of 2 and agent1 gets a reward of -2.
If you choose differently, you get a reward of -2 and agent1 gets a reward of 2.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 3. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your opponent is agent1.
You are selfish.


You and agent1 are playing a strictly zero-sum matching game: whatever one of you wins, the other loses. The unique equilibrium is in mixed strategies.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.

There are 1 rounds to decide.
The current round is number 1.

If you both choose the same option, you get a reward of 2 and agent1 gets a reward of -2.
If you choose differently, you get a reward of -2 and agent1 gets a reward of 2.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 4. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your opponent is agent2.
You are selfish.


You and agent2 are playing a strictly zero-sum matching game: whatever one of you wins, the other loses. The unique equilibrium is in mixed strategies.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.

There are 1 rounds to decide.
The current round is number 1.

If you both choose the same option, you get a reward of 2 and agent2 gets a reward of -2.
If you choose differently, you get a reward of -2 and agent2 gets a reward of 2.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```
