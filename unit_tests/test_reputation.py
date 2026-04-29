"""Tests for the {coopRateN} / {reputationN} prompt placeholders."""

from __future__ import annotations

import re
import unittest

from src.payoff_matrix import PayoffMatrix
from src.prompt_creator import PromptCreator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _matrix_data() -> dict:
    return {
        "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
        "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
        "combinations": {
            "c1": ["strategy1", "strategy1"],
            "c2": ["strategy2", "strategy2"],
        },
        "matrix": {"c1": ["weight1", "weight1"], "c2": ["weight4", "weight4"]},
    }


class _StubAgent:
    def __init__(self, name: str, personality: str = "neutral") -> None:
        self.name = name
        self.personality = personality
        self.opponent_personality_prob = 0.0


def _make_creator(
    reputation_window=None,
    reputation_applies: bool = True,
    template: str = (
        "{currentPlayerName} faces {opponent1} (coop rate {coopRate1}, "
        "reputation {reputation1}). {choose}: [Pick {strategy1} or {strategy2}.]"
    ),
) -> PromptCreator:
    pm = PayoffMatrix(_matrix_data(), "en")
    return PromptCreator(
        "en",
        template,
        n_rounds=10,
        n_rounds_known=False,
        payoff_matrix=pm,
        reputation_window=reputation_window,
        reputation_applies=reputation_applies,
    )


def _hist(rounds_strategies: list[str], opponent_name: str = "opp") -> dict:
    """Build a history dict from a list of strategies, one per round."""
    return {
        f"round_{i + 1}": {opponent_name: {"strategy": s}}
        for i, s in enumerate(rounds_strategies)
    }


# ---------------------------------------------------------------------------
# Aggregate cooperation rate
# ---------------------------------------------------------------------------

class TestFullHistoryRate(unittest.TestCase):
    def test_two_of_four_cooperated_yields_50_percent(self) -> None:
        creator = _make_creator()
        agent = _StubAgent("agent1")
        opp = _StubAgent("opp")
        history = _hist(["Cooperate", "Cooperate", "Defect", "Defect"])
        prompt = creator.fill_template(agent, [opp], 5, history, "choose")
        self.assertIn("coop rate 0.50", prompt)
        self.assertIn("reputation moderately cooperative", prompt)

    def test_all_cooperated_yields_100_percent(self) -> None:
        creator = _make_creator()
        prompt = creator.fill_template(
            _StubAgent("agent1"),
            [_StubAgent("opp")],
            5,
            _hist(["Cooperate"] * 6),
            "choose",
        )
        self.assertIn("coop rate 1.00", prompt)
        self.assertIn("reputation highly cooperative", prompt)

    def test_all_defected_yields_zero(self) -> None:
        creator = _make_creator()
        prompt = creator.fill_template(
            _StubAgent("agent1"),
            [_StubAgent("opp")],
            5,
            _hist(["Defect"] * 6),
            "choose",
        )
        self.assertIn("coop rate 0.00", prompt)
        self.assertIn("reputation uncooperative", prompt)

    def test_no_history_emits_unknown_label(self) -> None:
        creator = _make_creator()
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 1, {}, "choose"
        )
        self.assertIn("coop rate n/a", prompt)
        self.assertIn("reputation unknown", prompt)


# ---------------------------------------------------------------------------
# Reputation window
# ---------------------------------------------------------------------------

class TestReputationWindow(unittest.TestCase):
    def setUp(self) -> None:
        self.history = _hist(["Cooperate", "Cooperate", "Defect", "Defect"])

    def test_window_2_uses_last_two_rounds(self) -> None:
        creator = _make_creator(reputation_window=2)
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 5, self.history, "choose"
        )
        # Last 2 rounds were both Defect ⇒ 0.00.
        self.assertIn("coop rate 0.00", prompt)
        self.assertIn("reputation uncooperative", prompt)

    def test_window_larger_than_history_uses_all_rounds(self) -> None:
        creator = _make_creator(reputation_window=100)
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 5, self.history, "choose"
        )
        # 4 rounds, 2 cooperate ⇒ 0.50.
        self.assertIn("coop rate 0.50", prompt)

    def test_window_1_uses_only_most_recent_round(self) -> None:
        creator = _make_creator(reputation_window=1)
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 5, self.history, "choose"
        )
        # Last round was Defect ⇒ 0.00.
        self.assertIn("coop rate 0.00", prompt)


# ---------------------------------------------------------------------------
# Reputation label boundaries
# ---------------------------------------------------------------------------

class TestReputationLabel(unittest.TestCase):
    """Boundary points of the rate→label mapping. 0.25 / 0.50 / 0.75 are
    the documented thresholds; assert each side."""

    def _label_for_rate(self, rate: float) -> str:
        return PromptCreator._reputation_label(rate)

    def test_exactly_75_percent_maps_to_highly(self) -> None:
        self.assertEqual(self._label_for_rate(0.75), "highly cooperative")

    def test_just_below_75_maps_to_moderately(self) -> None:
        self.assertEqual(self._label_for_rate(0.749), "moderately cooperative")

    def test_exactly_50_percent_maps_to_moderately(self) -> None:
        self.assertEqual(self._label_for_rate(0.50), "moderately cooperative")

    def test_just_below_50_maps_to_occasionally(self) -> None:
        self.assertEqual(self._label_for_rate(0.499), "occasionally cooperative")

    def test_exactly_25_percent_maps_to_occasionally(self) -> None:
        self.assertEqual(self._label_for_rate(0.25), "occasionally cooperative")

    def test_just_below_25_maps_to_uncooperative(self) -> None:
        self.assertEqual(self._label_for_rate(0.249), "uncooperative")

    def test_zero_maps_to_uncooperative(self) -> None:
        self.assertEqual(self._label_for_rate(0.0), "uncooperative")

    def test_one_maps_to_highly_cooperative(self) -> None:
        self.assertEqual(self._label_for_rate(1.0), "highly cooperative")


# ---------------------------------------------------------------------------
# Multi-opponent + history holes
# ---------------------------------------------------------------------------

class TestMultiOpponent(unittest.TestCase):
    def test_each_opponent_has_independent_rate(self) -> None:
        template = (
            "{currentPlayerName} vs {opponent1} (coop rate {coopRate1}) and "
            "{opponent2} (coop rate {coopRate2}). {choose}: [Pick {strategy1} or {strategy2}.]"
        )
        creator = _make_creator(template=template)
        history = {
            "round_1": {
                "opp1": {"strategy": "Cooperate"},
                "opp2": {"strategy": "Defect"},
            },
            "round_2": {
                "opp1": {"strategy": "Cooperate"},
                "opp2": {"strategy": "Defect"},
            },
        }
        prompt = creator.fill_template(
            _StubAgent("agent1"),
            [_StubAgent("opp1"), _StubAgent("opp2")],
            3,
            history,
            "choose",
        )
        # opp1 cooperated both rounds → 1.00; opp2 never cooperated → 0.00.
        self.assertIn("opp1 (coop rate 1.00)", prompt)
        self.assertIn("opp2 (coop rate 0.00)", prompt)


class TestHistoryHoles(unittest.TestCase):
    def test_rounds_without_strategy_are_skipped(self) -> None:
        # If the opponent didn't play (e.g. game ended early for them),
        # those rounds don't count toward the rate.
        creator = _make_creator()
        history = {
            "round_1": {"opp": {"strategy": "Cooperate"}},
            "round_2": {"opp": {"strategy": None}},
            "round_3": {"opp": {"strategy": "Cooperate"}},
        }
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 4, history, "choose"
        )
        # 2 cooperate, 1 skipped ⇒ 2/2 = 1.00.
        self.assertIn("coop rate 1.00", prompt)

    def test_rounds_with_no_entry_for_opponent_are_skipped(self) -> None:
        creator = _make_creator()
        history = {
            "round_1": {"someone_else": {"strategy": "Cooperate"}},
            "round_2": {"opp": {"strategy": "Defect"}},
        }
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 3, history, "choose"
        )
        # Only one round counted (round 2 with Defect) ⇒ 0.00.
        self.assertIn("coop rate 0.00", prompt)

    def test_malformed_round_keys_yield_unknown(self) -> None:
        creator = _make_creator()
        history = {"not_a_round": {"opp": {"strategy": "Cooperate"}}}
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 1, history, "choose"
        )
        # Sort fails → method returns None → label is "unknown".
        self.assertIn("coop rate n/a", prompt)
        self.assertIn("reputation unknown", prompt)


# ---------------------------------------------------------------------------
# Placeholder hygiene
# ---------------------------------------------------------------------------

class TestReputationApplies(unittest.TestCase):
    """The ``reputation_applies`` flag must suppress reputation labels for
    games where 'cooperate' / 'defect' aren't meaningful (Battle of Sexes,
    Zero Sum, …)."""

    def setUp(self) -> None:
        self.history = _hist(["Cooperate", "Cooperate", "Cooperate", "Cooperate"])

    def test_applies_false_yields_unknown_even_with_full_history(self) -> None:
        creator = _make_creator(reputation_applies=False)
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 5, self.history, "choose"
        )
        # No coop-rate inference even though the opponent always cooperated.
        self.assertIn("coop rate n/a", prompt)
        self.assertIn("reputation unknown", prompt)

    def test_applies_true_inferences_remain_intact(self) -> None:
        # Default behaviour preserved when the flag is True.
        creator = _make_creator(reputation_applies=True)
        prompt = creator.fill_template(
            _StubAgent("agent1"), [_StubAgent("opp")], 5, self.history, "choose"
        )
        self.assertIn("coop rate 1.00", prompt)
        self.assertIn("reputation highly cooperative", prompt)

    def test_default_flag_value_is_true_for_backwards_compat(self) -> None:
        # Don't break existing callers that rely on auto-injection.
        from src.prompt_creator import PromptCreator as PC

        pm = PayoffMatrix(_matrix_data(), "en")
        # Construct without the new flag — must default to True.
        creator = PC(
            "en", "{coopRate1} {reputation1} {choose}: [Pick {strategy1}.]",
            n_rounds=1, n_rounds_known=False, payoff_matrix=pm,
        )
        self.assertTrue(creator.reputation_applies)


class TestPlaceholderHygiene(unittest.TestCase):
    def test_no_unfilled_placeholders_in_prompt(self) -> None:
        # If the template uses {coopRate1}/{reputation1}, the rendered prompt
        # must never contain a literal {coopRateN} substring.
        creator = _make_creator()
        prompt = creator.fill_template(
            _StubAgent("agent1"),
            [_StubAgent("opp")],
            3,
            _hist(["Cooperate", "Defect"]),
            "choose",
        )
        self.assertNotIn("{coopRate", prompt)
        self.assertNotIn("{reputation", prompt)

    def test_template_without_placeholders_runs_normally(self) -> None:
        # A template that doesn't reference reputation must still render.
        template = "{currentPlayerName} {choose}: [Pick {strategy1}.]"
        pm = PayoffMatrix(_matrix_data(), "en")
        creator = PromptCreator("en", template, 5, False, pm)
        prompt = creator.fill_template(
            _StubAgent("agent1"),
            [_StubAgent("opp")],
            1,
            _hist(["Cooperate"]),
            "choose",
        )
        self.assertEqual(
            prompt.strip(), "agent1 Pick Cooperate."
        )


if __name__ == "__main__":
    unittest.main()
