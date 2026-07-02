"""Payoff matrix lookup helpers used during a FAIRGAME round."""

from __future__ import annotations

from src.utils.logger import get_logger

logger = get_logger(__name__)


def label_to_key_map(strategies: dict[str, str]) -> dict[str, str]:
    """Invert a ``{strategy_key: display_label}`` mapping to label→key.

    History records the *localized display label* an agent played, so every
    consumer that needs the canonical key (baselines, belief scoring, regret,
    equilibrium metrics) performs this inversion. One shared helper instead
    of the same comprehension re-implemented at each site.
    """
    return {label: key for key, label in strategies.items()}


class PayoffMatrix:
    """Wraps the ``payoffMatrix`` config block and resolves combinations to scores.

    The matrix contains four named sub-structures: ``strategies`` (per-language
    labels), ``weights`` (numeric values), ``combinations`` (ordered strategy
    keys per combination) and ``matrix`` (weight keys per combination).
    """

    def __init__(self, matrix_data: dict, language: str) -> None:
        self.matrix_data = matrix_data
        self.language = language
        # Lazy O(1) lookup cache; built on first use because some callers
        # construct ``PayoffMatrix`` from the pre-transform schema where
        # ``combinations`` is a list of [strategy, weight] pairs.
        self._combo_by_strategies_cache: dict[tuple[str, ...], str] | None = None

    @property
    def _combo_by_strategies(self) -> dict[tuple[str, ...], str]:
        if self._combo_by_strategies_cache is None:
            self._combo_by_strategies_cache = {
                tuple(strats): combo_key
                for combo_key, strats in self.matrix_data["combinations"].items()
            }
        return self._combo_by_strategies_cache

    @property
    def strategies(self) -> dict[str, str]:
        return self.matrix_data["strategies"][self.language]

    @property
    def weights(self) -> dict[str, float]:
        return self.matrix_data["weights"]

    @property
    def matrix(self) -> dict[str, list[str]]:
        return self.matrix_data["matrix"]

    def get_weights_for_combination(self, strategy_list: list[str]) -> tuple[float, ...]:
        """Resolve ``strategy_list`` (display names) to a tuple of weight values."""
        name_to_key = label_to_key_map(self.strategies)
        try:
            key_list = [name_to_key[name] for name in strategy_list]
        except KeyError as missing:
            raise ValueError(f"Invalid strategy: {missing.args[0]}") from None

        combo_key = self._combo_by_strategies.get(tuple(key_list))
        if combo_key is None:
            raise ValueError("No matching combination found.")
        return tuple(self.weights[wk] for wk in self.matrix[combo_key])

    def get_combination_key(self, round_strategies: list[str]) -> str:
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

    def attribute_scores(self, agents, round_strategies: list[str]) -> None:
        """Attribute payoff weights to ``agents`` for the given combination."""
        combo_key = self.get_combination_key(round_strategies)
        weight_keys = list(self.matrix[combo_key])
        agents = list(agents)
        if len(weight_keys) < len(agents):
            # Fail loudly here: silently skipping the trailing agents leaves
            # them without a score for this round, which only blows up much
            # later (stale last_score / IndexError) far from the real cause.
            raise ValueError(
                f"Payoff matrix row {combo_key!r} defines {len(weight_keys)} "
                f"weights but the game has {len(agents)} agents."
            )
        for agent, agent_weight in zip(agents, weight_keys, strict=True):
            agent.add_score(self.weights[agent_weight])
