"""Expand a config's personality / opponent-prior axes into a DataFrame.

The factory used to fold this into ``compute_all_game_configurations`` /
``compute_configuration``. Extracting it here makes the responsibility
clear: given a config dict and a language, produce one row per game-to-be-
constructed, with one column per agent-position-by-attribute.

Symmetric dedup behaviour: when every agent shares an LLM, personality
and opponent-prior axes are expanded with
``itertools.combinations_with_replacement`` (so (cooperative, selfish)
and (selfish, cooperative) collapse). When LLMs differ per agent, the
full Cartesian product is taken because agent identity matters.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import Any

import pandas as pd


class PermutationExpander:
    """Build the per-language permutation DataFrame."""

    # ---- Public ---------------------------------------------------------

    def expand(self, config: dict[str, Any], language: str) -> pd.DataFrame:
        """Return a DataFrame of one row per (Agent, Personality, OpponentProb, LLM)
        combination for ``language``."""
        if config.get("allAgentPermutations"):
            df = self._all_permutations(language, config["agents"], config)
        else:
            df = self._single_configuration(language, config["agents"], config)
        df["Language"] = language
        return self._attach_llm_columns(df, config)

    # ---- LLM resolution -------------------------------------------------

    def resolve_llms(self, full_config: Any, agents: Sequence[str]) -> list[str]:
        """Resolve the per-agent LLM identifiers for ``agents``.

        Accepts:
          * a config dict with ``llms`` (list or dict) or ``llm`` (string)
          * a bare LLM identifier (legacy callers, kept for back-compat)
        """
        n_agents = len(agents)
        if isinstance(full_config, str):
            return [full_config] * n_agents
        llms = full_config.get("llms")
        if isinstance(llms, dict):
            return [llms[name] for name in agents]
        if isinstance(llms, (list, tuple)):
            llms_list = list(llms)
            if len(llms_list) != n_agents:
                raise ValueError(
                    f"config['llms'] length ({len(llms_list)}) "
                    f"must equal number of agents ({n_agents})."
                )
            return llms_list
        single = full_config.get("llm")
        if isinstance(single, str):
            return [single] * n_agents
        raise ValueError("Missing LLM configuration: provide 'llm', 'llms' list, or 'llms' dict.")

    # ---- Internals ------------------------------------------------------

    def _uses_same_llm_for_all(self, full_config: Any, agent_names: Sequence[str]) -> bool:
        try:
            llms = self.resolve_llms(full_config, agent_names)
        except Exception:
            return False
        return len(set(llms)) == 1

    def _all_permutations(
        self, language: str, config_agents: dict[str, Any], full_config: Any
    ) -> pd.DataFrame:
        n_agents = len(config_agents["names"])
        agent_combinations = [config_agents["names"]]

        # Each agent's assignment is the JOINT pair (personality, prior). We
        # must reduce symmetry / take the product over this joint per-agent
        # space — NOT over each axis independently. Reducing personality and
        # prior separately with ``combinations_with_replacement`` and then
        # crossing them dropped genuinely distinct joint assignments (e.g.
        # agent1=(coop,0.5), agent2=(selfish,0) could not be represented).
        per_agent_attrs = list(
            itertools.product(
                config_agents["personalities"][language],
                config_agents["opponentPersonalityProb"],
            )
        )

        same_llm = self._uses_same_llm_for_all(full_config, config_agents["names"])
        if same_llm:
            # Agents share an LLM, so agent identity is interchangeable:
            # collapse order-equivalent joint assignments.
            attr_perms = list(itertools.combinations_with_replacement(per_agent_attrs, n_agents))
        else:
            # Distinct LLMs → agent identity matters → full ordered product.
            attr_perms = list(itertools.product(per_agent_attrs, repeat=n_agents))

        rows = []
        for agents in agent_combinations:
            n = len(agents)
            for attr_tuple in attr_perms:
                rows.append(
                    {
                        **{f"Agent{i + 1}": agents[i] for i in range(n)},
                        **{f"Personality{i + 1}": attr_tuple[i][0] for i in range(n)},
                        **{f"OpponentPersonalityProb{i + 1}": attr_tuple[i][1] for i in range(n)},
                    }
                )
        return pd.DataFrame(rows)

    def _single_configuration(
        self, language: str, config_agents: dict[str, Any], full_config: Any
    ) -> pd.DataFrame:
        n_agents = len(config_agents["names"])
        row = {
            **{f"Agent{i + 1}": config_agents["names"][i] for i in range(n_agents)},
            **{
                f"Personality{i + 1}": config_agents["personalities"][language][i]
                for i in range(n_agents)
            },
            **{
                f"OpponentPersonalityProb{i + 1}": config_agents["opponentPersonalityProb"][i]
                for i in range(n_agents)
            },
        }
        return pd.DataFrame([row])

    def _attach_llm_columns(self, df: pd.DataFrame, full_config: Any) -> pd.DataFrame:
        if df.empty:
            return df

        agent_cols = sorted(
            (c for c in df.columns if c.startswith("Agent")),
            key=lambda x: int(x.replace("Agent", "")),
        )
        llm_cols = [f"LLM{i}" for i in range(1, len(agent_cols) + 1)]
        for col in llm_cols:
            if col not in df.columns:
                df[col] = None

        for idx, row in df.iterrows():
            agents = [row[c] for c in agent_cols]
            llms = self.resolve_llms(full_config, agents)
            for i, llm in enumerate(llms, start=1):
                df.at[idx, f"LLM{i}"] = llm
        return df
