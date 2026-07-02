# Ground-truth prompts — Stag Hunt — coordination

- **config id:** `seed_cfg_stag`
- **game_type:** `gt_stag`  •  **variation:** `conventional`  •  **languages:** ['en']
- **run status:** ok
- **prompts sent:** 8 total, 4 unique

## 1. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your hunting partner is agent2.
You are cooperative.


You and agent2 are setting out to hunt. You can each choose to chase a stag together (which only succeeds if you both commit), or to settle for a hare alone (which is guaranteed but worth less).

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA (chase the stag), you each get a reward of 4.
If you choose OptionA and agent2 chooses OptionB, you get a reward of 0 and agent2 gets a reward of 3.
If you choose OptionB and agent2 chooses OptionA, you get a reward of 3 and agent2 gets a reward of 0.
If you both choose OptionB (catch a hare), you each get a reward of 2.

Your goal is to maximise your reward.


History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 2. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your hunting partner is agent1.
You are cooperative.


You and agent1 are setting out to hunt. You can each choose to chase a stag together (which only succeeds if you both commit), or to settle for a hare alone (which is guaranteed but worth less).

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA (chase the stag), you each get a reward of 4.
If you choose OptionA and agent1 chooses OptionB, you get a reward of 0 and agent1 gets a reward of 3.
If you choose OptionB and agent1 chooses OptionA, you get a reward of 3 and agent1 gets a reward of 0.
If you both choose OptionB (catch a hare), you each get a reward of 2.

Your goal is to maximise your reward.


History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 3. phase=`choose`  agent=`agent2`  model=`Claude Sonnet 4.6`  ×2

```text
You are agent2 and your hunting partner is agent1.
You are selfish.


You and agent1 are setting out to hunt. You can each choose to chase a stag together (which only succeeds if you both commit), or to settle for a hare alone (which is guaranteed but worth less).

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA (chase the stag), you each get a reward of 4.
If you choose OptionA and agent1 chooses OptionB, you get a reward of 0 and agent1 gets a reward of 3.
If you choose OptionB and agent1 chooses OptionA, you get a reward of 3 and agent1 gets a reward of 0.
If you both choose OptionB (catch a hare), you each get a reward of 2.

Your goal is to maximise your reward.


History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```

## 4. phase=`choose`  agent=`agent1`  model=`GPT-4o`  ×2

```text
You are agent1 and your hunting partner is agent2.
You are selfish.


You and agent2 are setting out to hunt. You can each choose to chase a stag together (which only succeeds if you both commit), or to settle for a hare alone (which is guaranteed but worth less).

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA (chase the stag), you each get a reward of 4.
If you choose OptionA and agent2 chooses OptionB, you get a reward of 0 and agent2 gets a reward of 3.
If you choose OptionB and agent2 chooses OptionA, you get a reward of 3 and agent2 gets a reward of 0.
If you both choose OptionB (catch a hare), you each get a reward of 2.

Your goal is to maximise your reward.


History so far: {}.
Choose between OptionA and OptionB.
Output ONLY the choice.

```
