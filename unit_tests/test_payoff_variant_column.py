"""``payoff_variant_name`` round-trip from the saved configuration to the row.

When a configuration group is fanned out, each variant carries a unique
matrix; the resulting Run rows must include a stable column identifying
which variant produced them so the radar plot's S_P (sensitivity to
payoff) axis has something to compute.
"""

from __future__ import annotations

import unittest

from src.results_processing.agent_info import AgentInfo
from src.results_processing.game_data import GameData


class TestGameDataEmitsPayoffVariantColumn(unittest.TestCase):
    def _make_data(self, variant_name=None):
        return GameData(
            game_id="g0",
            language="en",
            n_rounds=1,
            n_rounds_is_known=True,
            agents_communicate=False,
            agents=[
                AgentInfo(name="a1", llm_service="L", personality="x", opponent_prob=0),
                AgentInfo(name="a2", llm_service="L", personality="y", opponent_prob=0),
            ],
            agents_round_data={
                "a1": {"strategies": ["A"], "scores": [1.0], "messages": [], "beliefs": []},
                "a2": {"strategies": ["A"], "scores": [1.0], "messages": [], "beliefs": []},
            },
            payoff_variant_name=variant_name,
        )

    def test_column_emitted_when_variant_name_provided(self) -> None:
        row = self._make_data(variant_name="harsh").to_dict()
        self.assertEqual(row["payoff_variant_name"], "harsh")

    def test_column_omitted_when_variant_name_is_none(self) -> None:
        # Leaf configurations (no group) shouldn't pollute the schema with
        # an always-None column.
        row = self._make_data(variant_name=None).to_dict()
        self.assertNotIn("payoff_variant_name", row)


if __name__ == "__main__":
    unittest.main()
