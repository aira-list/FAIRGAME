# Ground-truth prompts — Harmony Game — dominant cooperation

- **config id:** `seed_cfg_harmony`
- **game_type:** `gt_harmony`  •  **variation:** `conventional`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 8 total, 4 unique

## 1. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and the other player is agent2.
You are cooperative.


You and agent2 are working on a shared project. Cooperation strictly dominates: each of you is better off cooperating regardless of what the other does.

Every round each of you has the following choices: 'OptionA' (cooperate) and 'OptionB' (defect).

There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you each get a reward of 5.
If you choose OptionA and agent2 chooses OptionB, you get a reward of 3 and agent2 gets a reward of 2.
If you choose OptionB and agent2 chooses OptionA, you get a reward of 2 and agent2 gets a reward of 3.
If you both choose OptionB, you each get a reward of 1.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 2. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and the other player is agent1.
You are cooperative.


You and agent1 are working on a shared project. Cooperation strictly dominates: each of you is better off cooperating regardless of what the other does.

Every round each of you has the following choices: 'OptionA' (cooperate) and 'OptionB' (defect).

There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you each get a reward of 5.
If you choose OptionA and agent1 chooses OptionB, you get a reward of 3 and agent1 gets a reward of 2.
If you choose OptionB and agent1 chooses OptionA, you get a reward of 2 and agent1 gets a reward of 3.
If you both choose OptionB, you each get a reward of 1.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 3. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and the other player is agent1.
You are selfish.


You and agent1 are working on a shared project. Cooperation strictly dominates: each of you is better off cooperating regardless of what the other does.

Every round each of you has the following choices: 'OptionA' (cooperate) and 'OptionB' (defect).

There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you each get a reward of 5.
If you choose OptionA and agent1 chooses OptionB, you get a reward of 3 and agent1 gets a reward of 2.
If you choose OptionB and agent1 chooses OptionA, you get a reward of 2 and agent1 gets a reward of 3.
If you both choose OptionB, you each get a reward of 1.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 4. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and the other player is agent2.
You are selfish.


You and agent2 are working on a shared project. Cooperation strictly dominates: each of you is better off cooperating regardless of what the other does.

Every round each of you has the following choices: 'OptionA' (cooperate) and 'OptionB' (defect).

There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you each get a reward of 5.
If you choose OptionA and agent2 chooses OptionB, you get a reward of 3 and agent2 gets a reward of 2.
If you choose OptionB and agent2 chooses OptionA, you get a reward of 2 and agent2 gets a reward of 3.
If you both choose OptionB, you each get a reward of 1.

Your goal is to maximise your reward.
History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```
