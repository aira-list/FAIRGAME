# Ground-truth prompts — PD — mixed strategies (multi-seed + equilibria)

- **config id:** `seed_cfg_pd_mixed`
- **game_type:** `gt_pd`  •  **variation:** `mixed`  •  **languages:** ['en']
- **run status:** partial  (BeliefParseError: Belief response must be a non-empty JSON object.)
- **prompts sent:** 10 total, 1 unique

## 1. phase=`belief/mixed`  agent=`agent1`  model=`GPT-4o`  ×10

```text
You are agent1 and your opponent is agent2.
You are cooperative.

Every round each of you has the following choices: 'OptionA' and 'OptionB'.
There are 1 rounds to decide.
The current round is number 1.

If you both choose OptionA, you both get a penalty of 6.
If you choose OptionA and agent2 chooses OptionB, you get a penalty of 0 and agent2 gets a penalty of 10.
If you choose OptionB and agent2 chooses OptionA, you get a penalty of 10 and agent2 gets a penalty of 0.
If you both choose OptionB, you both get a penalty of 2.

History so far: {}.

Output your strategy as a JSON probability distribution like predict the opponent: {"OptionA": 0.6, "OptionB": 0.4}. Output ONLY the JSON.

```
