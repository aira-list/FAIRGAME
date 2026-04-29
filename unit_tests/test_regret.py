"""Tests for :mod:`src.results_processing.regret`."""

from __future__ import annotations

import unittest

from src.results_processing.regret import best_response_payoff, regret_per_round


def _pd_matrix() -> dict:
    """Standard PD payoff matrix in the canonical FAIRGAME shape."""
    return {
        "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
        "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
        "combinations": {
            "combination1": ["strategy1", "strategy1"],
            "combination2": ["strategy1", "strategy2"],
            "combination3": ["strategy2", "strategy1"],
            "combination4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "combination1": ["weight1", "weight1"],
            "combination2": ["weight3", "weight2"],
            "combination3": ["weight2", "weight3"],
            "combination4": ["weight4", "weight4"],
        },
    }


class TestBestResponsePayoff(unittest.TestCase):
    def test_against_cooperator_defect_pays_more(self) -> None:
        # If opponent plays Cooperate (strategy1), defecting pays weight2 = 10
        # and cooperating pays weight1 = 6. Best response: 10.
        best = best_response_payoff(_pd_matrix(), "en", 0, ["Cooperate"])
        self.assertEqual(best, 10)

    def test_against_defector_defect_pays_more(self) -> None:
        # If opponent plays Defect (strategy2), cooperating pays weight3 = 0,
        # defecting pays weight4 = 2. Best response: 2.
        best = best_response_payoff(_pd_matrix(), "en", 0, ["Defect"])
        self.assertEqual(best, 2)

    def test_returns_none_when_matrix_is_incomplete(self) -> None:
        partial = {"strategies": {"en": {"strategy1": "Cooperate"}}}
        self.assertIsNone(best_response_payoff(partial, "en", 0, ["Cooperate"]))


class TestRegretPerRound(unittest.TestCase):
    def test_full_regret_when_cooperated_against_defector(self) -> None:
        # Played Cooperate, got 0; best response (Defect) was 2 → regret 2.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate"],
            own_scores=[0],
            others_strategies_per_round=[["Defect"]],
        )
        self.assertEqual(regret, [2.0])

    def test_zero_regret_for_best_response(self) -> None:
        # Defected against a defector: got 2, best response was 2 → regret 0.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Defect"],
            own_scores=[2],
            others_strategies_per_round=[["Defect"]],
        )
        self.assertEqual(regret, [0.0])

    def test_returns_none_for_unparseable_round(self) -> None:
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Defect"],
            own_scores=[0],  # short scores list
            others_strategies_per_round=[["Defect"], ["Cooperate"]],
        )
        self.assertEqual(regret[0], 2.0)
        self.assertIsNone(regret[1])  # missing score → None


if __name__ == "__main__":
    unittest.main()
