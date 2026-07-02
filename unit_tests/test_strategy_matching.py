"""Unit tests for ``GameRound._match_strategy`` label resolution.

Covers the three-tier preference order (exact label, single mention, last
mention) and, in particular, the substring-overlap tiebreak: when two labels
start at the same position in the reply, the longer/more-specific one wins
rather than whichever happens to come first in dict order.
"""

import unittest
from types import SimpleNamespace

from src.game_round import GameRound


def _round(strategies: dict[str, str]) -> GameRound:
    game = SimpleNamespace(
        current_round=1,
        fake_communication_config=None,
        payoff_matrix=SimpleNamespace(strategies=strategies),
    )
    return GameRound(game)


class TestMatchStrategy(unittest.TestCase):
    def test_exact_label_wins(self) -> None:
        r = _round({"c": "Cooperate", "d": "Defect"})
        self.assertEqual(r._match_strategy("Cooperate"), "c")
        self.assertEqual(r._match_strategy("  defect. "), "d")

    def test_single_mention_in_prose(self) -> None:
        r = _round({"c": "Cooperate", "d": "Defect"})
        self.assertEqual(r._match_strategy("I think I will Defect this time"), "d")

    def test_last_mention_wins_when_several_appear(self) -> None:
        r = _round({"c": "Cooperate", "d": "Defect"})
        self.assertEqual(r._match_strategy("Rather than Cooperate, I Defect"), "d")

    def test_substring_overlap_prefers_longer_label(self) -> None:
        # "Cooperate" is a substring of "Cooperate more"; both start at the
        # same position, so the more specific (longer) label must win
        # regardless of dict insertion order.
        strategies = {"c": "Cooperate", "cm": "Cooperate more"}
        self.assertEqual(_round(strategies)._match_strategy("Cooperate more"), "cm")

    def test_substring_overlap_independent_of_dict_order(self) -> None:
        forward = {"c": "Cooperate", "cm": "Cooperate more"}
        reverse = {"cm": "Cooperate more", "c": "Cooperate"}
        self.assertEqual(_round(forward)._match_strategy("I will Cooperate more"), "cm")
        self.assertEqual(_round(reverse)._match_strategy("I will Cooperate more"), "cm")

    def test_no_label_present_returns_none(self) -> None:
        r = _round({"c": "Cooperate", "d": "Defect"})
        self.assertIsNone(r._match_strategy("no idea what to do"))


if __name__ == "__main__":
    unittest.main()
