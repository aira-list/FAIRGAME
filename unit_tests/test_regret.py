"""Tests for :mod:`src.results_processing.regret`.

One behaviour per test, robust assertions: edge cases, error paths,
invariants, multi-agent matrices, ties, and clamping.
"""

from __future__ import annotations

import unittest

from src.results_processing.regret import best_response_payoff, regret_per_round


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _pd_matrix() -> dict:
    """Canonical 2x2 Prisoner's Dilemma. Defection (strategy2) dominates."""
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


def _tie_matrix() -> dict:
    """Both strategies pay the same — best-response is *either*; max payoff is shared."""
    return {
        "weights": {"weight1": 5, "weight2": 5},
        "strategies": {"en": {"strategy1": "A", "strategy2": "B"}},
        "combinations": {
            "combination1": ["strategy1", "strategy1"],
            "combination2": ["strategy1", "strategy2"],
            "combination3": ["strategy2", "strategy1"],
            "combination4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "combination1": ["weight1", "weight1"],
            "combination2": ["weight1", "weight2"],
            "combination3": ["weight2", "weight1"],
            "combination4": ["weight2", "weight2"],
        },
    }


def _negative_matrix() -> dict:
    """Zero-sum-style matrix with negative weights."""
    return {
        "weights": {"weight1": 5, "weight2": -5},
        "strategies": {"en": {"strategy1": "A", "strategy2": "B"}},
        "combinations": {
            "combination1": ["strategy1", "strategy1"],
            "combination2": ["strategy1", "strategy2"],
            "combination3": ["strategy2", "strategy1"],
            "combination4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "combination1": ["weight1", "weight2"],
            "combination2": ["weight2", "weight1"],
            "combination3": ["weight2", "weight1"],
            "combination4": ["weight1", "weight2"],
        },
    }


def _three_player_matrix() -> dict:
    """Complete 3-player 2-strategy matrix (8 combinations).

    Each agent's payoff is the count of others playing strategy1 +
    bonus 2 if the agent plays strategy2. So strategy2 weakly dominates
    for every agent under any opponent profile.
    """
    return {
        "weights": {"w0": 0, "w1": 1, "w2": 2, "w3": 3, "w4": 4},
        "strategies": {"en": {"strategy1": "A", "strategy2": "B"}},
        "combinations": {
            "combo_AAA": ["strategy1", "strategy1", "strategy1"],
            "combo_AAB": ["strategy1", "strategy1", "strategy2"],
            "combo_ABA": ["strategy1", "strategy2", "strategy1"],
            "combo_BAA": ["strategy2", "strategy1", "strategy1"],
            "combo_ABB": ["strategy1", "strategy2", "strategy2"],
            "combo_BAB": ["strategy2", "strategy1", "strategy2"],
            "combo_BBA": ["strategy2", "strategy2", "strategy1"],
            "combo_BBB": ["strategy2", "strategy2", "strategy2"],
        },
        # weight = (others-playing-A count) + (2 if self plays B else 0).
        "matrix": {
            "combo_AAA": ["w2", "w2", "w2"],  # everyone has 2 others on A
            "combo_AAB": ["w1", "w1", "w4"],
            "combo_ABA": ["w1", "w4", "w1"],
            "combo_BAA": ["w4", "w1", "w1"],
            "combo_ABB": ["w0", "w3", "w3"],
            "combo_BAB": ["w3", "w0", "w3"],
            "combo_BBA": ["w3", "w3", "w0"],
            "combo_BBB": ["w2", "w2", "w2"],
        },
    }


# ---------------------------------------------------------------------------
# best_response_payoff
# ---------------------------------------------------------------------------

class TestBestResponseAgainstFixedOpponent(unittest.TestCase):
    """Behavioural tests of best-response selection."""

    def test_against_cooperator_defection_is_best(self) -> None:
        # Opp plays C → defect pays 10, cooperate pays 6 → best = 10.
        self.assertEqual(
            best_response_payoff(_pd_matrix(), "en", 0, ["Cooperate"]), 10
        )

    def test_against_defector_defection_is_best(self) -> None:
        # Opp plays D → defect pays 2, cooperate pays 0 → best = 2.
        self.assertEqual(
            best_response_payoff(_pd_matrix(), "en", 0, ["Defect"]), 2
        )

    def test_returns_max_payoff_under_ties(self) -> None:
        # Both strategies pay 5 against either opponent ⇒ best = 5 (not None).
        self.assertEqual(best_response_payoff(_tie_matrix(), "en", 0, ["A"]), 5)
        self.assertEqual(best_response_payoff(_tie_matrix(), "en", 0, ["B"]), 5)

    def test_handles_negative_payoffs(self) -> None:
        # Against opponent A, agent at index 0 plays A → 5 or B → -5. Best = 5.
        self.assertEqual(best_response_payoff(_negative_matrix(), "en", 0, ["A"]), 5)
        # Against opponent B, A → -5, B → 5. Best = 5.
        self.assertEqual(best_response_payoff(_negative_matrix(), "en", 0, ["B"]), 5)

    def test_three_player_best_response_index_0(self) -> None:
        # Agent 0, others (A, A): A→AAA pays 2; B→BAA pays 4. Best = 4.
        self.assertEqual(
            best_response_payoff(_three_player_matrix(), "en", 0, ["A", "A"]), 4
        )

    def test_three_player_best_response_higher_index(self) -> None:
        # Agent at middle (index 1), others (A, A): A→AAA pays 2; B→ABA pays 4.
        self.assertEqual(
            best_response_payoff(_three_player_matrix(), "en", 1, ["A", "A"]), 4
        )

    def test_three_player_best_response_last_index(self) -> None:
        # Agent at index 2, others (A, A): A→AAA pays 2; B→AAB pays 4.
        self.assertEqual(
            best_response_payoff(_three_player_matrix(), "en", 2, ["A", "A"]), 4
        )

    def test_returns_none_when_strategies_block_missing(self) -> None:
        m = _pd_matrix()
        m["strategies"] = {}
        self.assertIsNone(best_response_payoff(m, "en", 0, ["Cooperate"]))

    def test_returns_none_when_language_missing(self) -> None:
        m = _pd_matrix()
        self.assertIsNone(best_response_payoff(m, "fr", 0, ["Cooperate"]))

    def test_returns_none_when_combinations_block_missing(self) -> None:
        m = _pd_matrix()
        m.pop("combinations")
        self.assertIsNone(best_response_payoff(m, "en", 0, ["Cooperate"]))

    def test_returns_none_when_matrix_block_missing(self) -> None:
        m = _pd_matrix()
        m.pop("matrix")
        self.assertIsNone(best_response_payoff(m, "en", 0, ["Cooperate"]))

    def test_returns_none_when_weights_block_missing(self) -> None:
        m = _pd_matrix()
        m.pop("weights")
        self.assertIsNone(best_response_payoff(m, "en", 0, ["Cooperate"]))

    def test_returns_none_when_opponent_label_unknown(self) -> None:
        # The matrix has no "Treason" — should fail closed, not crash.
        self.assertIsNone(best_response_payoff(_pd_matrix(), "en", 0, ["Treason"]))

    def test_returns_none_when_an_alternative_combination_is_missing(self) -> None:
        # Engine integrity: if the matrix doesn't include every (own,
        # others) combination needed to compute the max, the function
        # MUST return None rather than silently picking from a partial
        # set. Otherwise regret is under-stated.
        m = _three_player_matrix()
        # Remove BAA — agent 0 with others (A, A) needs BAA to evaluate
        # its B-strategy alternative.
        del m["combinations"]["combo_BAA"]
        del m["matrix"]["combo_BAA"]
        self.assertIsNone(best_response_payoff(m, "en", 0, ["A", "A"]))

    def test_returns_none_when_matrix_lacks_weight_keys_for_combination(self) -> None:
        # Combination present in ``combinations`` but missing from
        # ``matrix``. Agent 0 against opponent D needs CD=combination2
        # (own=C → strategy1+strategy2 = combination2). Removing the
        # weight keys for combination2 must cause a None return.
        m = _pd_matrix()
        del m["matrix"]["combination2"]
        self.assertIsNone(best_response_payoff(m, "en", 0, ["Defect"]))


# ---------------------------------------------------------------------------
# regret_per_round
# ---------------------------------------------------------------------------

class TestRegretPerRound(unittest.TestCase):
    def test_full_regret_when_cooperated_against_defector(self) -> None:
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
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Defect"],
            own_scores=[2],
            others_strategies_per_round=[["Defect"]],
        )
        self.assertEqual(regret, [0.0])

    def test_returns_none_for_round_with_missing_score(self) -> None:
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Defect"],
            own_scores=[0],  # length-1, second round has no score
            others_strategies_per_round=[["Defect"], ["Cooperate"]],
        )
        self.assertEqual(regret[0], 2.0)
        self.assertIsNone(regret[1])

    def test_returns_none_for_round_with_missing_opponent_data(self) -> None:
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Defect"],
            own_scores=[0, 2],
            others_strategies_per_round=[["Defect"]],  # second round absent
        )
        self.assertEqual(regret[0], 2.0)
        self.assertIsNone(regret[1])

    def test_regret_is_never_negative(self) -> None:
        # Even if the recorded score exceeds the matrix-best (e.g. the
        # utility transform inflated it), regret must clamp to 0.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Defect", "Defect"],
            own_scores=[1000.0, 1000.0],  # absurdly high
            others_strategies_per_round=[["Defect"], ["Defect"]],
        )
        for r in regret:
            self.assertIsNotNone(r)
            self.assertGreaterEqual(r, 0.0)

    def test_regret_invariant_length_matches_own_strategies(self) -> None:
        # The result list must have one entry per round of own_strategies.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Defect", "Cooperate"],
            own_scores=[0, 2, 6],
            others_strategies_per_round=[["Defect"], ["Defect"], ["Cooperate"]],
        )
        self.assertEqual(len(regret), 3)

    def test_non_numeric_score_recorded_as_none(self) -> None:
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate"],
            own_scores=["not-a-number"],
            others_strategies_per_round=[["Defect"]],
        )
        self.assertEqual(regret, [None])

    def test_negative_payoff_matrix_produces_meaningful_regret(self) -> None:
        # Played strategy2 against opp A → got -5; best response was strategy1 → 5.
        # Regret = 5 - (-5) = 10.
        regret = regret_per_round(
            _negative_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["B"],
            own_scores=[-5],
            others_strategies_per_round=[["A"]],
        )
        self.assertEqual(regret, [10.0])

    def test_three_player_regret(self) -> None:
        # 3-player: agent 0 plays A in AAA → realised payoff 2.
        # Best response B → BAA pays 4 → regret = 4 - 2 = 2.
        regret = regret_per_round(
            _three_player_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["A"],
            own_scores=[2],
            others_strategies_per_round=[["A", "A"]],
        )
        self.assertEqual(regret, [2.0])

    def test_empty_inputs_produce_empty_output(self) -> None:
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=[],
            own_scores=[],
            others_strategies_per_round=[],
        )
        self.assertEqual(regret, [])

    def test_short_others_does_not_truncate_output(self) -> None:
        # Three rounds of own play but only one round of opponent data.
        # Rounds 1 and 2 have nothing to look up — they should resolve to
        # None, but the output list MUST still have length 3 (one entry
        # per own round). A short-circuit `break` would silently drop the
        # tail, hiding the data gap from downstream aggregation.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Defect", "Cooperate"],
            own_scores=[0, 2, 6],
            others_strategies_per_round=[["Defect"]],
        )
        self.assertEqual(len(regret), 3)
        self.assertIsNotNone(regret[0])
        self.assertIsNone(regret[1])
        self.assertIsNone(regret[2])

    def test_unknown_opponent_label_does_not_truncate_subsequent_rounds(self) -> None:
        # Round 0 has a bogus opponent label, so best=None and round 0's
        # regret is None. Round 1 is a normal play and MUST still produce
        # a numeric regret — the bad round must not break the loop.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Cooperate"],
            own_scores=[0, 0],
            others_strategies_per_round=[["Treason"], ["Defect"]],
        )
        self.assertEqual(len(regret), 2)
        self.assertIsNone(regret[0])
        self.assertEqual(regret[1], 2.0)

    def test_non_numeric_score_does_not_truncate_subsequent_rounds(self) -> None:
        # Round 0 has a non-numeric score (regret unrecoverable), but
        # round 1 is well-formed. The bad round must record None and the
        # loop MUST continue to round 1.
        regret = regret_per_round(
            _pd_matrix(),
            language="en",
            agent_index=0,
            own_strategies=["Cooperate", "Cooperate"],
            own_scores=["nope", 0],
            others_strategies_per_round=[["Defect"], ["Defect"]],
        )
        self.assertEqual(len(regret), 2)
        self.assertIsNone(regret[0])
        self.assertEqual(regret[1], 2.0)


# ---------------------------------------------------------------------------
# best_response_payoff — corrupt-matrix edge cases (mutmut-driven coverage)
# ---------------------------------------------------------------------------

class TestBestResponseCorruptMatrix(unittest.TestCase):
    def test_returns_none_when_weight_keys_shorter_than_agent_index(self) -> None:
        # A combination's weight-keys row is too short for the given
        # agent_index. The function MUST guard against indexing past the
        # end (returning None) rather than allowing an IndexError. This
        # covers the boundary ``agent_index == len(weight_keys)``.
        m = _pd_matrix()
        m["matrix"]["combination3"] = ["weight2"]  # length 1, not 2
        # Agent 1 against opponent "Defect": needs combination3 (own=C
        # opponent=D from agent 1's perspective is rows differently
        # indexed). Use a setup that actually hits combination3.
        m["matrix"]["combination4"] = ["weight4"]  # also length 1, force the path
        result = best_response_payoff(m, "en", 1, ["Defect"])
        self.assertIsNone(result)

    def test_default_payoff_is_zero_when_weight_key_missing_from_weights(self) -> None:
        # If a combination references a weight name that's not declared
        # in ``weights``, that branch's payoff falls back to 0 — never to
        # an arbitrary positive number that would inflate best-response.
        m = {
            "weights": {"w_lo": 0.5},  # no "w_missing"
            "strategies": {"en": {"strategy1": "A", "strategy2": "B"}},
            "combinations": {
                "c_aa": ["strategy1", "strategy1"],
                "c_ab": ["strategy1", "strategy2"],
                "c_ba": ["strategy2", "strategy1"],
                "c_bb": ["strategy2", "strategy2"],
            },
            "matrix": {
                "c_aa": ["w_missing", "w_lo"],  # agent 0's A/A weight is missing
                "c_ab": ["w_lo", "w_lo"],
                "c_ba": ["w_lo", "w_lo"],
                "c_bb": ["w_lo", "w_lo"],
            },
        }
        # Against opponent A, agent 0's two options are:
        #   A → weights.get("w_missing", 0) = 0.0
        #   B → weights["w_lo"]            = 0.5
        # The max MUST be 0.5, not 1.0 (which would be the case if the
        # default were silently changed to a non-zero value).
        self.assertEqual(best_response_payoff(m, "en", 0, ["A"]), 0.5)


if __name__ == "__main__":
    unittest.main()
