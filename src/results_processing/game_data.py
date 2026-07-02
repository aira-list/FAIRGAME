"""Per-game DataFrame row assembler."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.payoff_matrix import label_to_key_map
from src.results_processing.agent_info import AgentInfo
from src.results_processing.belief_metrics import aggregate_metrics, per_round_metrics
from src.results_processing.game_metrics import equilibrium_metrics, welfare_summary
from src.results_processing.regret import regret_per_round
from src.results_processing.row_schema import AgentCol, Col, agent_col
from src.results_processing.trust_metrics import trust_summary


class GameData:
    """Encapsulates all relevant data for a single game.

    Static fields (id, language, agent metadata) are flattened into a single
    DataFrame row alongside per-agent round-level lists (strategies, scores,
    messages, beliefs) and aggregate metrics — Theory-of-Mind belief
    accuracy, equilibrium-distance, and welfare.
    """

    def __init__(
        self,
        game_id: str,
        language: str | None,
        n_rounds: int | None,
        n_rounds_is_known: bool,
        agents_communicate: bool,
        agents: list[AgentInfo],
        agents_round_data: dict[str, dict[str, list[Any]]],
        elicit_beliefs: bool = False,
        tom_order: int = 1,
        equilibria: Sequence[str] = (),
        payoff_matrix_summary: dict[str, Any] | None = None,
        language_for_matrix: str | None = None,
        pareto_optimal_sum: float | None = None,
        seed: int | None = None,
        payoff_variant_name: str | None = None,
        record_messages: bool | None = None,
    ) -> None:
        self.game_id = game_id
        self.language = language
        self.n_rounds = n_rounds
        self.n_rounds_is_known = n_rounds_is_known
        self.agents_communicate = agents_communicate
        self.agents = agents
        self.agents_round_data = agents_round_data
        self.elicit_beliefs = elicit_beliefs
        self.tom_order = tom_order
        self.equilibria = list(equilibria)
        self.payoff_matrix_summary = payoff_matrix_summary
        self.language_for_matrix = language_for_matrix
        self.pareto_optimal_sum = pareto_optimal_sum
        self.seed = seed
        self.payoff_variant_name = payoff_variant_name
        # Whether the game recorded messages at all: true real communication,
        # but also fake/covert channels (fakeCommunication) where the config's
        # ``agents_communicate`` flag is off yet messages exist in history.
        self.record_messages = agents_communicate if record_messages is None else record_messages

    # ---- Public ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        # Number of rounds for which *every* agent has a recorded strategy.
        # Use ``min`` (not ``max``): on ragged / early-stop data only the
        # common rounds carry complete pairwise data, and that's what the
        # regret / welfare / equilibrium metrics actually compute on. ``max``
        # over-reported the played-round count relative to those metrics.
        played_rounds = (
            min(len(d["strategies"]) for d in self.agents_round_data.values())
            if self.agents_round_data
            else 0
        )
        row: dict[str, Any] = {
            Col.GAME_ID: self.game_id,
            Col.LANGUAGE: self.language,
            Col.N_ROUNDS_IS_KNOWN: self.n_rounds_is_known,
            Col.MAX_ROUNDS: self.n_rounds,
            Col.PLAYED_ROUNDS: played_rounds,
            Col.AGENTS_COMMUNICATE: self.agents_communicate,
            Col.ELICIT_BELIEFS: self.elicit_beliefs,
            Col.TOM_ORDER: self.tom_order,
        }
        if self.seed is not None:
            row[Col.SEED] = self.seed
        if self.payoff_variant_name is not None:
            # Stable per-row tag identifying which payoff variant produced
            # this game; lets the radar plot's sensitivity-to-payoff axis
            # average across rows that differ ONLY in the matrix.
            row[Col.PAYOFF_VARIANT_NAME] = self.payoff_variant_name

        all_agent_names = [agent.name for agent in self.agents]

        for idx, agent in enumerate(self.agents, start=1):
            prefix = f"agent{idx}_"
            row.update(agent.to_dict(prefix=prefix))

            agent_name = agent.name
            round_data = self.agents_round_data.get(
                agent_name,
                {"strategies": [], "scores": [], "messages": [], "beliefs": []},
            )
            row[agent_col(idx, AgentCol.STRATEGIES)] = round_data["strategies"]
            row[agent_col(idx, AgentCol.SCORES)] = round_data["scores"]
            row[agent_col(idx, AgentCol.MESSAGES)] = (
                round_data["messages"] if self.record_messages else []
            )

            if self.elicit_beliefs:
                row[agent_col(idx, AgentCol.BELIEFS)] = round_data.get("beliefs", [])
                row[agent_col(idx, AgentCol.BELIEFS_2ND_ORDER)] = round_data.get(
                    "beliefs_2nd_order", []
                )
                row.update(self._belief_metrics_for(agent_name, all_agent_names, prefix))
                row.update(
                    self._second_order_belief_metrics_for(agent_name, all_agent_names, prefix)
                )

            row.update(self._regret_metrics_for(idx - 1, agent_name, prefix))
            row.update(self._trust_metrics_for(agent_name, prefix))

        # Game-level analyses ------------------------------------------------
        row.update(self._equilibrium_metrics_block())
        row.update(self._welfare_metrics_block())

        return row

    # ---- Regret metrics -------------------------------------------------

    def _regret_metrics_for(self, agent_index: int, agent_name: str, prefix: str) -> dict[str, Any]:
        """Per-agent regret per round and the average."""
        if not self.payoff_matrix_summary:
            return {}
        own = self.agents_round_data.get(agent_name, {})
        own_strategies: list[str] = list(own.get("strategies", []) or [])
        if not own_strategies:
            return {}

        # Build the *other-agents'* strategies list per round, in canonical order.
        ordered_others = [a.name for a in self.agents if a.name != agent_name]
        n_rounds = min(
            len(own_strategies),
            min(
                (
                    len(self.agents_round_data.get(n, {}).get("strategies", []))
                    for n in ordered_others
                ),
                default=len(own_strategies),
            ),
        )
        others_per_round: list[list[str]] = []
        for r in range(n_rounds):
            others_per_round.append(
                [self.agents_round_data[name]["strategies"][r] for name in ordered_others]
            )

        regret = regret_per_round(
            self.payoff_matrix_summary,
            self.language_for_matrix or "en",
            agent_index,
            own_strategies[:n_rounds],
            others_per_round,
        )
        valid = [v for v in regret if v is not None]
        out: dict[str, Any] = {prefix + AgentCol.REGRET_PER_ROUND: regret}
        out[prefix + AgentCol.REGRET_MEAN] = sum(valid) / len(valid) if valid else None
        return out

    # ---- Trust / monitoring metrics -------------------------------------

    def _trust_metrics_for(self, agent_name: str, prefix: str) -> dict[str, Any]:
        """Per-agent monitoring columns, emitted only when the game used trust."""
        data = self.agents_round_data.get(agent_name, {})
        actions = list(data.get("trust_actions", []) or [])
        if not any(a for a in actions):
            return {}
        costs = list(data.get("trust_costs", []) or [])
        summary = trust_summary(actions, costs)
        return {
            prefix + AgentCol.TRUST_ACTIONS: actions,
            prefix + AgentCol.LOOK_RATE: summary["look_rate"],
            prefix + AgentCol.MONITORING_COST_TOTAL: summary["monitoring_cost_total"],
        }

    # ---- Belief metrics -------------------------------------------------

    def _belief_metrics_for(
        self,
        agent_name: str,
        all_agent_names: list[str],
        prefix: str,
    ) -> dict[str, Any]:
        own = self.agents_round_data.get(agent_name, {})
        beliefs = own.get("beliefs", []) or []
        if not beliefs:
            return {}

        opponents = [name for name in all_agent_names if name != agent_name]
        if not opponents:
            return {}

        per_round_aggregated: list[dict[str, float] | None] = []
        n_rounds = len(beliefs)
        for round_idx in range(n_rounds):
            round_metrics: list[dict[str, float]] = []
            for opp in opponents:
                opp_strategies = self.agents_round_data.get(opp, {}).get("strategies", [])
                if round_idx >= len(opp_strategies):
                    continue
                metrics = per_round_metrics([beliefs[round_idx]], [opp_strategies[round_idx]])[0]
                if metrics is not None:
                    round_metrics.append(metrics)
            if round_metrics:
                per_round_aggregated.append(
                    {
                        "brier": sum(m["brier"] for m in round_metrics) / len(round_metrics),
                        "p_outcome": sum(m["p_outcome"] for m in round_metrics)
                        / len(round_metrics),
                        "agreement": sum(m["agreement"] for m in round_metrics)
                        / len(round_metrics),
                    }
                )
            else:
                per_round_aggregated.append(None)

        agg = aggregate_metrics(per_round_aggregated)
        return {
            prefix + AgentCol.BELIEF_BRIER_PER_ROUND: [
                m["brier"] if m else None for m in per_round_aggregated
            ],
            prefix + AgentCol.BELIEF_MEAN_BRIER: agg["mean_brier"],
            prefix + AgentCol.BELIEF_MEAN_P_OUTCOME: agg["mean_p_outcome"],
            prefix + AgentCol.BELIEF_AGREEMENT_RATE: agg["agreement_rate"],
        }

    # ---- Second-order belief metrics ------------------------------------

    def _second_order_belief_metrics_for(
        self,
        agent_name: str,
        all_agent_names: list[str],
        prefix: str,
    ) -> dict[str, Any]:
        """Score this agent's 2nd-order beliefs against opponents' 1st-order ones.

        For each round, this agent's 2nd-order belief is a distribution
        over its OWN strategies (predicting the opponent's belief about
        the agent). The ground truth is the opponent's 1st-order belief
        from the same round (a distribution over the same strategies).

        With more than two agents we average per-round Brier across
        opponents; the resulting per-round + mean column shape mirrors
        the existing 1st-order belief metrics.
        """
        from src.results_processing.belief_metrics import (
            brier_score_distribution,
        )

        own = self.agents_round_data.get(agent_name, {})
        beliefs_2nd: list[dict[str, float] | None] = list(own.get("beliefs_2nd_order", []) or [])
        if not any(b for b in beliefs_2nd):
            return {}

        opponents = [name for name in all_agent_names if name != agent_name]
        if not opponents:
            return {}

        per_round_brier: list[float | None] = []
        for round_idx, predicted in enumerate(beliefs_2nd):
            if not predicted:
                per_round_brier.append(None)
                continue
            scores = []
            for opp in opponents:
                opp_beliefs = self.agents_round_data.get(opp, {}).get("beliefs", [])
                if round_idx >= len(opp_beliefs):
                    continue
                target = opp_beliefs[round_idx]
                if not target:
                    continue
                scores.append(brier_score_distribution(predicted, target))
            per_round_brier.append((sum(scores) / len(scores)) if scores else None)

        valid = [s for s in per_round_brier if s is not None]
        return {
            prefix + AgentCol.BELIEF_2ND_ORDER_PER_ROUND_BRIER: per_round_brier,
            prefix + AgentCol.BELIEF_2ND_ORDER_MEAN_BRIER: (
                sum(valid) / len(valid) if valid else None
            ),
        }

    # ---- Equilibrium ----------------------------------------------------

    def _equilibrium_metrics_block(self) -> dict[str, Any]:
        if not self.equilibria:
            return {}
        combos = self._combination_keys_per_round()
        metrics = equilibrium_metrics(combos, self.equilibria)
        return {
            "equilibria": list(self.equilibria),
            "equilibrium_per_round": metrics["equilibrium_per_round"],
            "equilibrium_rate": metrics["equilibrium_rate"],
            "first_equilibrium_round": metrics["first_equilibrium_round"],
        }

    def _combination_keys_per_round(self) -> list[str | None]:
        if not self.payoff_matrix_summary or not self.language_for_matrix:
            return []
        strategies = (self.payoff_matrix_summary.get("strategies") or {}).get(
            self.language_for_matrix
        ) or {}
        if not strategies:
            return []
        # display label -> canonical key
        label_to_key = label_to_key_map(strategies)
        combinations = self.payoff_matrix_summary.get("combinations") or {}
        # tuple of strategy keys -> combination name
        combo_lookup = {tuple(v): k for k, v in combinations.items()}

        ordered_agents = [agent.name for agent in self.agents]
        n_rounds = max(
            (len(self.agents_round_data.get(n, {}).get("strategies", [])) for n in ordered_agents),
            default=0,
        )
        keys: list[str | None] = []
        for r in range(n_rounds):
            choices: list[str | None] = []
            for name in ordered_agents:
                strategies_played = self.agents_round_data.get(name, {}).get("strategies", [])
                if r >= len(strategies_played):
                    choices.append(None)
                    continue
                label = strategies_played[r]
                choices.append(label_to_key.get(label))
            if any(c is None for c in choices):
                keys.append(None)
                continue
            keys.append(combo_lookup.get(tuple(choices)))
        return keys

    # ---- Welfare --------------------------------------------------------

    def _welfare_metrics_block(self) -> dict[str, Any]:
        per_agent_scores = {
            name: data.get("scores", []) for name, data in self.agents_round_data.items()
        }
        if not any(scores for scores in per_agent_scores.values()):
            return {}
        return welfare_summary(per_agent_scores, pareto_optimal_sum=self.pareto_optimal_sum)
