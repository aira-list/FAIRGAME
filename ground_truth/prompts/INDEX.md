# Ground-truth prompt capture — index

One file per configuration (per variant for groups). Prompts are the exact text sent to agents; captured with a stub LLM (no real calls).

| config | variant | status | #prompts | note |
| --- | --- | --- | --- | --- |
| `seed_cfg_pd_baseline_tournament` | — | ok | 0 |  |
| `seed_cfg_pd_llm` | — | ok | 8 |  |
| `seed_cfg_pd_comm` | — | ok | 16 |  |
| `seed_cfg_pd_covert` | — | ok | 8 |  |
| `seed_cfg_pd_tom` | — | ok | 128 |  |
| `seed_cfg_pd_mixed` | — | partial | 10 | BeliefParseError: Belief response must be a non-empty JSON object. |
| `seed_cfg_pd_trust` | — | ok | 16 |  |
| `seed_cfg_pd_fehr` | — | ok | 8 |  |
| `seed_cfg_pd_crra` | — | ok | 8 |  |
| `seed_cfg_pd_pool` | — | ok | 162 |  |
| `seed_cfg_pd_multilang` | — | ok | 16 |  |
| `seed_cfg_pd_sweep` | mild | ok | 8 |  |
| `seed_cfg_pd_sweep` | harsh | ok | 8 |  |
| `seed_cfg_pd_horizon` | — | ok | 68 |  |
| `seed_cfg_stag` | — | ok | 8 |  |
| `seed_cfg_snowdrift` | — | ok | 8 |  |
| `seed_cfg_harmony` | — | ok | 8 |  |
| `seed_cfg_battle` | — | ok | 160 |  |
| `seed_cfg_volunteer` | — | ok | 3 |  |
| `seed_cfg_zerosum` | — | ok | 8 |  |
| `seed_cfg_pd_interaction` | — | ok | 16 |  |