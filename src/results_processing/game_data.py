"""Per-game DataFrame row assembler."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from src.results_processing.agent_info import AgentInfo
from src.results_processing.belief_metrics import aggregate_metrics, per_round_metrics
from src.results_processing.game_metrics import equilibrium_metrics, welfare_summary


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
        language: Optional[str],
        n_rounds: Optional[int],
        n_rounds_is_known: bool,
        agents_communicate: bool,
        agents: List[AgentInfo],
        agents_round_data: Dict[str, Dict[str, List[Any]]],
        elicit_beliefs: bool = False,
        tom_order: int = 1,
        equilibria: Sequence[str] = (),
        payoff_matrix_summary: Optional[Dict[str, Any]] = None,
        language_for_matrix: Optional[str] = None,
        pareto_optimal_sum: Optional[float] = None,
        seed: Optional[int] = None,
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

    # ---- Public ---------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        played_rounds = (
            max(len(d["strategies"]) for d in self.agents_round_data.values())
            if self.agents_round_data
            else 0
        )
        row: Dict[str, Any] = {
            "game_id": self.game_id,
            "language": self.language,
            "n_rounds_is_known": self.n_rounds_is_known,
            "max_rounds": self.n_rounds,
            "played_rounds": played_rounds,
            "agents_communicate": self.agents_communicate,
            "elicit_beliefs": self.elicit_beliefs,
            "tom_order": self.tom_order,
        }
        if self.seed is not None:
            row["seed"] = self.seed

        all_agent_names = [agent.name for agent in self.agents]

        for idx, agent in enumerate(self.agents, start=1):
            prefix = f"agent{idx}_"
            row.update(agent.to_dict(prefix=prefix))

            agent_name = agent.name
            round_data = self.agents_round_data.get(
                agent_name,
                {"strategies": [], "scores": [], "messages": [], "beliefs": []},
            )
            row[f"{prefix}strategies"] = round_data["strategies"]
            row[f"{prefix}scores"] = round_data["scores"]
            row[f"{prefix}messages"] = (
                round_data["messages"] if self.agents_communicate else []
            )

            if self.elicit_beliefs:
                row[f"{prefix}beliefs"] = round_data.get("beliefs", [])
                row.update(
                    self._belief_metrics_for(agent_name, all_agent_names, prefix)
                )

        # Game-level analyses ------------------------------------------------
        row.update(self._equilibrium_metrics_block())
        row.update(self._welfare_metrics_block())

        return row

    # ---- Belief metrics -------------------------------------------------

    def _belief_metrics_for(
        self,
        agent_name: str,
        all_agent_names: List[str],
        prefix: str,
    ) -> Dict[str, Any]:
        own = self.agents_round_data.get(agent_name, {})
        beliefs = own.get("beliefs", []) or []
        if not beliefs:
            return {}

        opponents = [name for name in all_agent_names if name != agent_name]
        if not opponents:
            return {}

        per_round_aggregated: List[Optional[Dict[str, float]]] = []
        n_rounds = len(beliefs)
        for round_idx in range(n_rounds):
            round_metrics: List[Dict[str, float]] = []
            for opp in opponents:
                opp_strategies = self.agents_round_data.get(opp, {}).get("strategies", [])
                if round_idx >= len(opp_strategies):
                    continue
                metrics = per_round_metrics(
                    [beliefs[round_idx]], [opp_strategies[round_idx]]
                )[0]
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
            f"{prefix}belief_brier_per_round": [
                m["brier"] if m else None for m in per_round_aggregated
            ],
            f"{prefix}belief_mean_brier": agg["mean_brier"],
            f"{prefix}belief_mean_p_outcome": agg["mean_p_outcome"],
            f"{prefix}belief_agreement_rate": agg["agreement_rate"],
        }

    # ---- Equilibrium ----------------------------------------------------

    def _equilibrium_metrics_block(self) -> Dict[str, Any]:
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

    def _combination_keys_per_round(self) -> List[Optional[str]]:
        if not self.payoff_matrix_summary or not self.language_for_matrix:
            return []
        strategies = (self.payoff_matrix_summary.get("strategies") or {}).get(
            self.language_for_matrix
        ) or {}
        if not strategies:
            return []
        # display label -> canonical key
        label_to_key = {label: key for key, label in strategies.items()}
        combinations = self.payoff_matrix_summary.get("combinations") or {}
        # tuple of strategy keys -> combination name
        combo_lookup = {tuple(v): k for k, v in combinations.items()}

        ordered_agents = [agent.name for agent in self.agents]
        n_rounds = max(
            (len(self.agents_round_data.get(n, {}).get("strategies", [])) for n in ordered_agents),
            default=0,
        )
        keys: List[Optional[str]] = []
        for r in range(n_rounds):
            choices: List[Optional[str]] = []
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

    def _welfare_metrics_block(self) -> Dict[str, Any]:
        per_agent_scores = {
            name: data.get("scores", [])
            for name, data in self.agents_round_data.items()
        }
        if not any(scores for scores in per_agent_scores.values()):
            return {}
        return welfare_summary(
            per_agent_scores, pareto_optimal_sum=self.pareto_optimal_sum
        )
