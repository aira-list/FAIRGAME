"""Regression tests for exponential history growth in ToM belief games.

Bug: the belief / second-order belief phases stored the *full rendered
prompt* (``belief_prompt`` / ``belief_2nd_order_prompt``) into
``GameHistory.rounds``. That same ``rounds`` dict is rendered into the next
prompt via the ``{history}`` placeholder, so every prompt re-embedded all
prior prompts — history grew ~exponentially round over round and a 5-round
ToM-2 game exhausted memory (~21 GB) and froze the suite.

Fix: ``GameHistory.prompt_view()`` returns a history view that excludes the
bulky ``*_prompt`` audit fields. ``GameRound`` feeds that view to the prompt,
while ``describe()`` keeps the prompts for results/output.
"""

from __future__ import annotations

import unittest

from src.game_history import GameHistory


class TestPromptViewExcludesPrompts(unittest.TestCase):
    def _history_with_prompts(self) -> GameHistory:
        h = GameHistory()
        big_prompt = "X" * 5000  # stand-in for a rendered prompt
        h.update_round(1, "agent1", {"strategy": "Cooperate", "belief": {"Cooperate": 0.7}})
        h.update_round(1, "agent1", {"belief_prompt": big_prompt})
        h.update_round(1, "agent1", {"belief_2nd_order_prompt": big_prompt})
        return h

    def test_prompt_view_drops_prompt_fields(self) -> None:
        view = self._history_with_prompts().prompt_view()
        agent = view["round_1"]["agent1"]
        # The bulky, self-referential prompt fields must be gone.
        self.assertNotIn("belief_prompt", agent)
        self.assertNotIn("belief_2nd_order_prompt", agent)
        # The genuine game data the LLM needs must survive.
        self.assertEqual(agent["strategy"], "Cooperate")
        self.assertEqual(agent["belief"], {"Cooperate": 0.7})

    def test_prompt_view_rendering_stays_small(self) -> None:
        # Even with 5 KB prompts stored, the prompt-facing view renders tiny.
        rendered = str(self._history_with_prompts().prompt_view())
        self.assertLess(len(rendered), 1000)

    def test_describe_still_carries_prompts(self) -> None:
        # The audit/output contract is unchanged: describe() keeps the prompts.
        summary = self._history_with_prompts().describe()
        row = summary["round_1"][0]
        self.assertEqual(len(row["belief_prompt"]), 5000)
        self.assertEqual(len(row["belief_2nd_order_prompt"]), 5000)

    def test_prompt_view_does_not_mutate_rounds(self) -> None:
        h = self._history_with_prompts()
        h.prompt_view()
        # Underlying storage must be untouched (describe() still needs prompts).
        self.assertIn("belief_prompt", h.rounds["round_1"]["agent1"])


class TestHistoryGrowthIsLinear(unittest.TestCase):
    """Simulate the game's feed-back loop and assert no exponential blow-up.

    Mirrors what GameRound does: each round it (1) renders a 'prompt' that
    embeds the current prompt-facing history, then (2) stores that rendered
    prompt back into history. With the fix, the stored prompt is excluded
    from the next render, so the per-round prompt size stays bounded.
    """

    def test_prompt_size_bounded_across_rounds(self) -> None:
        h = GameHistory()
        sizes = []
        for rnd in range(1, 11):
            for phase in ("belief_prompt", "belief_2nd_order_prompt"):
                # Render the prompt the way fill_template would: embed history.
                rendered = f"history so far: {h.prompt_view()}"
                sizes.append(len(rendered))
                # Store the rendered prompt back into history (the old bug).
                h.update_round(rnd, "agent1", {phase: rendered})
            h.update_round(rnd, "agent1", {"strategy": "Cooperate"})

        # If history nested prompts, sizes would roughly multiply each step.
        # With the fix they grow at most linearly with the number of rounds.
        self.assertLess(max(sizes), 5000, f"prompt sizes exploded: {sizes}")


if __name__ == "__main__":
    unittest.main()
