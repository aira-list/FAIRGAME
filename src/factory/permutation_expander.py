"""Expand a config's personality / opponent-prior axes into a DataFrame.

The factory used to fold this into ``compute_all_game_configurations`` /
``compute_configuration``. Extracting it here makes the responsibility
clear: given a config dict and a language, produce one row per game-to-be-
constructed, with one column per agent-position-by-attribute.

Symmetric dedup behaviour: when every agent shares an LLM, the game is
position-symmetric (payoff matrix invariant under permuting the agents)
and real communication is off, personality and opponent-prior axes are
expanded with ``itertools.combinations_with_replacement`` (so
(cooperative, selfish) and (selfish, cooperative) collapse). Otherwise —
per-agent LLMs, an asymmetric matrix such as Battle of the Sexes, or a
live message channel (the second speaker conditions on the first's
same-round message) — agent position matters and the full Cartesian
product is taken.

Pool values are deduplicated before expansion: a pool like
``["neutral", "neutral"]`` describes one condition, not two, and
repeating it would silently run (and statistically over-weight)
duplicate games.
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

    @staticmethod
    def _positions_interchangeable(full_config: Any) -> bool:
        """Whether swapping agent positions provably leaves the game unchanged.

        Position matters when real communication is on (messages are produced
        sequentially in agent order) or when the payoff matrix is not
        invariant under permuting the agents. A missing matrix keeps the
        legacy collapse; a matrix present but not in the canonical
        ``{combo: [strategy_keys]}`` / ``{combo: [weight_keys]}`` shape can't
        be proven symmetric, so it is treated as position-sensitive.
        """
        if not isinstance(full_config, dict):
            return True
        if full_config.get("agentsCommunicate"):
            return False
        pm = full_config.get("payoffMatrix")
        if not pm:
            return True

        combinations = pm.get("combinations") or {}
        weight_matrix = pm.get("matrix") or {}
        weights = pm.get("weights") or {}
        payoff_by_profile: dict[tuple[str, ...], tuple[float, ...]] = {}
        for combo, strategy_keys in combinations.items():
            weight_keys = weight_matrix.get(combo)
            if (
                not isinstance(strategy_keys, (list, tuple))
                or not all(isinstance(s, str) for s in strategy_keys)
                or not isinstance(weight_keys, (list, tuple))
                or len(weight_keys) != len(strategy_keys)
            ):
                return False  # non-canonical shape: cannot prove symmetry
            try:
                payoff_by_profile[tuple(strategy_keys)] = tuple(
                    float(weights[k]) for k in weight_keys
                )
            except (KeyError, TypeError, ValueError):
                return False
        if not payoff_by_profile:
            return True

        for profile, payoffs in payoff_by_profile.items():
            n = len(profile)
            for perm in itertools.permutations(range(n)):
                permuted_profile = tuple(profile[i] for i in perm)
                permuted_payoffs = tuple(payoffs[i] for i in perm)
                if payoff_by_profile.get(permuted_profile) != permuted_payoffs:
                    return False
        return True

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
        # dict.fromkeys: dedupe while preserving pool order. Repeated pool
        # values (e.g. every agent "neutral") describe one condition each —
        # expanding them verbatim multiplied identical games.
        per_agent_attrs = list(
            dict.fromkeys(
                itertools.product(
                    config_agents["personalities"][language],
                    config_agents["opponentPersonalityProb"],
                )
            )
        )

        interchangeable = self._uses_same_llm_for_all(
            full_config, config_agents["names"]
        ) and self._positions_interchangeable(full_config)
        if interchangeable:
            # Same LLM in a position-symmetric game: collapse order-equivalent
            # joint assignments.
            attr_perms = list(itertools.combinations_with_replacement(per_agent_attrs, n_agents))
        else:
            # Position matters (distinct LLMs, asymmetric payoffs, or a live
            # message channel) → full ordered product.
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
