"""Belief metrics must compare beliefs and outcomes in ONE namespace.

Regression test: the belief parser stores distributions with canonical role
keys ({"strategy1": p, "strategy2": q}) while the game history records the
opponent's move as a display label ("OptionB"). Before the fix these never
matched, so a 99%-confident correct forecast scored as maximally wrong
(Brier ~1, agreement 0) in every Theory-of-Mind run.
"""

from __future__ import annotations

import unittest

from src.results_processing.agent_info import AgentInfo
from src.results_processing.game_data import GameData
from unit_tests.support import canonical_pd_matrix


def _agents():
    return [
        AgentInfo(name="agent1", llm_service="fake", personality="neutral", opponent_prob=0.0),
        AgentInfo(name="agent2", llm_service="fake", personality="neutral", opponent_prob=0.0),
    ]


def _game(beliefs_agent1):
    return GameData(
        game_id="g0",
        language="en",
        n_rounds=2,
        n_rounds_is_known=True,
        agents_communicate=False,
        agents=_agents(),
        agents_round_data={
            "agent1": {
                "strategies": ["OptionA", "OptionA"],
                "scores": [3.0, 3.0],
                "messages": [],
                "beliefs": beliefs_agent1,
            },
            "agent2": {
                # Opponent plays label "OptionB" (= strategy2) both rounds.
                "strategies": ["OptionB", "OptionB"],
                "scores": [5.0, 5.0],
                "messages": [],
                "beliefs": [],
            },
        },
        elicit_beliefs=True,
        payoff_matrix_summary=canonical_pd_matrix(
            labels={"strategy1": "OptionA", "strategy2": "OptionB"}
        ),
        language_for_matrix="en",
    )


class TestBeliefNamespaceNormalisation(unittest.TestCase):
    def test_role_keyed_beliefs_score_against_label_outcomes(self) -> None:
        # Agent1 predicts strategy2 (= "OptionB") with 99% confidence — and
        # the opponent indeed plays OptionB. A correct forecast must score
        # near-perfect, not near-maximally-wrong.
        row = _game(
            [
                {"strategy1": 0.01, "strategy2": 0.99},
                {"strategy1": 0.01, "strategy2": 0.99},
            ]
        ).to_dict()
        self.assertEqual(row["agent1_belief_agreement_rate"], 1.0)
        self.assertAlmostEqual(row["agent1_belief_mean_p_outcome"], 0.99, places=6)
        self.assertLess(row["agent1_belief_mean_brier"], 0.01)

    def test_label_keyed_beliefs_still_score_correctly(self) -> None:
        # Some connectors answer with display labels — both namespaces must
        # keep working (normalisation is idempotent).
        row = _game(
            [
                {"OptionA": 0.01, "OptionB": 0.99},
                {"OptionA": 0.01, "OptionB": 0.99},
            ]
        ).to_dict()
        self.assertEqual(row["agent1_belief_agreement_rate"], 1.0)
        self.assertLess(row["agent1_belief_mean_brier"], 0.01)

    def test_wrong_forecast_still_scores_badly(self) -> None:
        # Sanity: the fix must not inflate genuinely wrong forecasts.
        row = _game(
            [
                {"strategy1": 0.99, "strategy2": 0.01},
                {"strategy1": 0.99, "strategy2": 0.01},
            ]
        ).to_dict()
        self.assertEqual(row["agent1_belief_agreement_rate"], 0.0)
        self.assertGreater(row["agent1_belief_mean_brier"], 1.9)
