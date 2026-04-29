"""Payoff matrix lookup helpers used during a FAIRGAME round."""

from __future__ import annotations

from typing import Dict, List, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PayoffMatrix:
    """Wraps the ``payoffMatrix`` config block and resolves combinations to scores.

    The matrix contains four named sub-structures: ``strategies`` (per-language
    labels), ``weights`` (numeric values), ``combinations`` (ordered strategy
    keys per combination) and ``matrix`` (weight keys per combination).
    """

    def __init__(self, matrix_data: Dict, language: str) -> None:
        self.matrix_data = matrix_data
        self.language = language
        # Lazy O(1) lookup cache; built on first use because some callers
        # construct ``PayoffMatrix`` from the pre-transform schema where
        # ``combinations`` is a list of [strategy, weight] pairs.
        self._combo_by_strategies_cache: Dict[Tuple[str, ...], str] | None = None

    @property
    def _combo_by_strategies(self) -> Dict[Tuple[str, ...], str]:
        if self._combo_by_strategies_cache is None:
            self._combo_by_strategies_cache = {
                tuple(strats): combo_key
                for combo_key, strats in self.matrix_data["combinations"].items()
            }
        return self._combo_by_strategies_cache

    @property
    def strategies(self) -> Dict[str, str]:
        return self.matrix_data["strategies"][self.language]

    @property
    def weights(self) -> Dict[str, float]:
        return self.matrix_data["weights"]

    @property
    def matrix(self) -> Dict[str, List[str]]:
        return self.matrix_data["matrix"]

    def get_weights_for_combination(self, strategy_list: List[str]) -> Tuple[float, ...]:
        """Resolve ``strategy_list`` (display names) to a tuple of weight values."""
        name_to_key = {name: key for key, name in self.strategies.items()}
        try:
            key_list = [name_to_key[name] for name in strategy_list]
        except KeyError as missing:
            raise ValueError(f"Invalid strategy: {missing.args[0]}") from None

        combo_key = self._combo_by_strategies.get(tuple(key_list))
        if combo_key is None:
            raise ValueError("No matching combination found.")
        return tuple(self.weights[wk] for wk in self.matrix[combo_key])

    def get_combination_key(self, round_strategies: List[str]) -> str:
        """Return the combination key whose strategy keys match ``round_strategies``."""
        combo_key = self._combo_by_strategies.get(tuple(round_strategies))
        if combo_key is None:
            logger.error(
                "Combination not found. Choices=%s available=%s",
                round_strategies,
                list(self._combo_by_strategies.keys()),
            )
            raise ValueError("Combination not found.")
        return combo_key

    def attribute_scores(self, agents, round_strategies: List[str]) -> None:
        """Attribute payoff weights to ``agents`` for the given combination."""
        combo_key = self.get_combination_key(round_strategies)
        weight_keys = list(self.matrix[combo_key])

        for agent in agents:
            if not weight_keys:
                break
            agent_weight = weight_keys.pop(0)
            agent.add_score(self.weights[agent_weight])
