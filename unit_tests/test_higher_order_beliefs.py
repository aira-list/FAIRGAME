"""Tests for B1: higher-order belief elicitation.

The engine already supports first-order beliefs via the ``believe``
phase. B1 adds second-order beliefs: each agent is asked "what does
your opponent think *you* will do?" and the engine stores its answer.

A 2nd-order belief is a probability distribution over the agent's
*own* strategy keys (predicting what the opponent predicts about the
agent). The ground truth for scoring it is the opponent's *actual*
1st-order belief (the opponent's own elicited distribution from the
same round).

Tests cover:

* phases_for_game wires in a BeliefSecondOrderPhase iff
  elicit_beliefs is on AND tom_order >= 2.
* The PHASE_BLOCKS tuple in PromptCreator recognises "believe2" as a
  phase block alongside the existing "believe".
* GameRound exposes a execute_belief_second_order_phase that records
  the elicited distribution under ``belief_2nd_order`` in history.
* When second-order elicitation parses, the parsed value is a probability
  distribution keyed by the agent's own strategy keys.
"""

from __future__ import annotations

import json
import unittest

from src.fake_message_generator import FakeCommunicationConfig
from src.phases import (
    BeliefPhase,
    BeliefSecondOrderPhase,
    ChoosePhase,
    phases_for_game,
)
from src.prompt_creator import PHASE_BLOCKS
from src.trust import TrustConfig
from unit_tests.support import canonical_pd_matrix


class _StubGame:
    """Mirrors the GameConfig-backed contract: the collaborator configs are
    always present (disabled by default), never None/missing."""

    agents_communicate = False
    elicit_beliefs = False
    tom_order = 1
    fake_communication_config = FakeCommunicationConfig(enabled=False)
    trust_config = TrustConfig(enabled=False)


# ---------------------------------------------------------------------------
# phases_for_game wiring
# ---------------------------------------------------------------------------


class TestPhasesForGameWithSecondOrder(unittest.TestCase):
    def test_no_second_order_phase_when_beliefs_off(self) -> None:
        class G(_StubGame):
            elicit_beliefs = False
            tom_order = 2

        self.assertNotIn(
            BeliefSecondOrderPhase,
            [type(p) for p in phases_for_game(G())],
        )

    def test_no_second_order_phase_when_tom_order_below_2(self) -> None:
        class G(_StubGame):
            elicit_beliefs = True
            tom_order = 1

        types = [type(p) for p in phases_for_game(G())]
        self.assertIn(BeliefPhase, types)
        self.assertNotIn(BeliefSecondOrderPhase, types)

    def test_second_order_phase_present_when_beliefs_and_tom2(self) -> None:
        class G(_StubGame):
            elicit_beliefs = True
            tom_order = 2

        types = [type(p) for p in phases_for_game(G())]
        self.assertIn(BeliefPhase, types)
        self.assertIn(BeliefSecondOrderPhase, types)
        # Must run BEFORE choose so the recorded belief reflects the
        # agent's pre-action prediction.
        self.assertLess(types.index(BeliefSecondOrderPhase), types.index(ChoosePhase))
        # Second-order runs AFTER first-order.
        self.assertLess(types.index(BeliefPhase), types.index(BeliefSecondOrderPhase))

    def test_second_order_phase_at_tom_order_3_too(self) -> None:
        class G(_StubGame):
            elicit_beliefs = True
            tom_order = 3

        self.assertIn(
            BeliefSecondOrderPhase,
            [type(p) for p in phases_for_game(G())],
        )

    def test_default_tom_order_yields_no_second_order_phase(self) -> None:
        # Pin the typed default: tom_order defaults to 1 on GameConfig, and
        # the baseline must be *no* second-order phase. A default of 2 would
        # silently enable it for every belief-elicitation run.
        class G(_StubGame):
            elicit_beliefs = True
            # NB: tom_order inherits the stub's default (1), mirroring
            # GameConfig's declared default.

        self.assertNotIn(
            BeliefSecondOrderPhase,
            [type(p) for p in phases_for_game(G())],
        )


# ---------------------------------------------------------------------------
# PromptCreator phase-block routing
# ---------------------------------------------------------------------------


class TestBelieveTwoBlock(unittest.TestCase):
    def test_believe2_is_in_phase_blocks(self) -> None:
        # PHASE_BLOCKS controls which {name}: [...] markers the engine
        # recognises as phase blocks. Without this, "believe2" would be
        # treated as a normal placeholder and not get pruned/kept by phase.
        self.assertIn("believe2", PHASE_BLOCKS)


# ---------------------------------------------------------------------------
# GameRound delegation + history bookkeeping
# ---------------------------------------------------------------------------


class TestGameRoundExecutesSecondOrderPhase(unittest.TestCase):
    def test_phase_run_delegates_to_round_runner(self) -> None:
        recorded = {}

        class _StubRunner:
            def execute_belief_second_order_phase(self) -> None:
                recorded["called"] = True

        BeliefSecondOrderPhase().run(_StubRunner())
        self.assertTrue(recorded.get("called"))

    def test_round_runner_stores_belief_under_belief_2nd_order(self) -> None:
        # Build the smallest GameRound-shaped object that exercises the
        # second-order entry point. We mock the agent's ``execute_round``
        # to return a JSON distribution and assert it lands in history.
        from src.game_round import GameRound
        from src.payoff_matrix import PayoffMatrix

        matrix = PayoffMatrix(
            canonical_pd_matrix(labels={"strategy1": "Coop", "strategy2": "Defect"}),
            "en",
        )

        class _Agent:
            def __init__(self, name: str) -> None:
                self.name = name
                self.personality = "neutral"
                self.opponent_personality_prob = 0.0

            def execute_round(self, prompt: str) -> str:
                return json.dumps({"Coop": 0.7, "Defect": 0.3})

        class _History:
            def __init__(self) -> None:
                self.rounds = {}

            def update_round(self, n, name, payload):
                bucket = self.rounds.setdefault(f"round_{n}", {}).setdefault(name, {})
                bucket.update(payload)

            def prompt_view(self):
                return self.rounds

        class _StubGame:
            language = "en"
            n_rounds = 1
            n_rounds_known = True
            agents_communicate = False
            elicit_beliefs = True
            tom_order = 2
            mixed_strategies = False
            current_round = 1
            payoff_matrix = matrix
            prompt_template = (
                "{intro}: [You are {personality}.]\n"
                "{believe2}: [Predict opponent's belief about you. JSON only.]"
            )
            agents = {}
            fake_communication_config = None
            history = _History()

        game = _StubGame()
        a1, a2 = _Agent("agent1"), _Agent("agent2")
        game.agents = {"agent1": a1, "agent2": a2}

        round_ = GameRound(game)
        round_.execute_belief_second_order_phase()

        # Both agents' second-order beliefs land in history.
        for name in ("agent1", "agent2"):
            recorded = game.history.rounds["round_1"][name].get("belief_2nd_order")
            self.assertIsNotNone(
                recorded,
                f"{name}: belief_2nd_order missing from history payload",
            )
            # The parsed distribution covers both strategy keys, sums to ~1.
            self.assertEqual(set(recorded.keys()), {"strategy1", "strategy2"})
            self.assertAlmostEqual(sum(recorded.values()), 1.0, places=5)

    def test_skips_when_template_has_no_believe2_block(self) -> None:
        # When the prompt template lacks a {believe2}: block we must
        # silently skip the phase — calling the LLM would either trigger
        # retry storms (no instructions to predict anything) or pollute
        # history with garbage. Pin the skip so a future refactor that
        # drops the guard gets caught.
        from src.game_round import GameRound
        from src.payoff_matrix import PayoffMatrix

        matrix = PayoffMatrix(
            canonical_pd_matrix(labels={"strategy1": "Coop", "strategy2": "Defect"}),
            "en",
        )

        execute_calls: list[str] = []

        class _Agent:
            def __init__(self, name: str) -> None:
                self.name = name
                self.personality = "neutral"
                self.opponent_personality_prob = 0.0

            def execute_round(self, prompt: str) -> str:
                execute_calls.append(prompt)
                return json.dumps({"Coop": 0.5, "Defect": 0.5})

        class _History:
            def __init__(self) -> None:
                self.rounds: dict = {}

            def update_round(self, n, name, payload):
                bucket = self.rounds.setdefault(f"round_{n}", {}).setdefault(name, {})
                bucket.update(payload)

            def prompt_view(self):
                return self.rounds

        class _StubGame:
            language = "en"
            n_rounds = 1
            n_rounds_known = True
            agents_communicate = False
            elicit_beliefs = True
            tom_order = 2
            mixed_strategies = False
            current_round = 1
            payoff_matrix = matrix
            # NB: no {believe2}: block — only the regular pieces.
            prompt_template = (
                "{intro}: [You are {personality}.]\n{believe}: [Predict opponent. JSON only.]"
            )
            agents: dict = {}
            fake_communication_config = None
            history = _History()

        game = _StubGame()
        game.agents = {"a1": _Agent("a1"), "a2": _Agent("a2")}

        round_ = GameRound(game)
        round_.execute_belief_second_order_phase()

        # No prompts sent; no history rows written.
        self.assertEqual(execute_calls, [])
        self.assertEqual(game.history.rounds, {})


# ---------------------------------------------------------------------------
# ResultsProcessor capture: belief_2nd_order entries on history actions must
# survive the _extract_agent_round_data → game_data → DataFrame pipeline.
# ---------------------------------------------------------------------------


class TestResultsProcessorCapturesSecondOrderBeliefs(unittest.TestCase):
    def test_extract_picks_up_belief_2nd_order_from_history_actions(self) -> None:
        # Pin the engine→DataFrame plumbing: if the action dict's
        # `belief_2nd_order` key is silently renamed by a refactor (or
        # the line gets dropped), the round-data dict must carry it
        # through unchanged.
        from src.results_processing.results_processor import ResultsProcessor

        history = {
            "round_1": [
                {
                    "agent": "a1",
                    "strategy": "Coop",
                    "score": 3,
                    "belief": {"Coop": 0.6, "Defect": 0.4},
                    "belief_2nd_order": {"Coop": 0.7, "Defect": 0.3},
                },
                {"agent": "a2", "strategy": "Coop", "score": 3},
            ],
            "round_2": [
                {
                    "agent": "a1",
                    "strategy": "Defect",
                    "score": 5,
                    "belief": {"Coop": 0.2, "Defect": 0.8},
                    "belief_2nd_order": {"Coop": 0.4, "Defect": 0.6},
                },
            ],
        }
        rp = ResultsProcessor()
        out = rp._extract_agent_round_data(history, "a1", record_messages=False)
        self.assertEqual(
            out["beliefs_2nd_order"],
            [
                {"Coop": 0.7, "Defect": 0.3},
                {"Coop": 0.4, "Defect": 0.6},
            ],
        )
        # Non-matching agent's data must not leak into a1's slot.
        out2 = rp._extract_agent_round_data(history, "a2", record_messages=False)
        self.assertEqual(out2["beliefs_2nd_order"], [None])

    def test_extract_records_none_when_2nd_order_belief_missing(self) -> None:
        # If a round's action has no `belief_2nd_order` key (e.g. ToM
        # was off that round, or the parse failed silently), the slot
        # must be `None` — not skipped, not 0, not an empty dict — so
        # downstream alignment with `strategies` / `beliefs` stays
        # round-by-round.
        from src.results_processing.results_processor import ResultsProcessor

        history = {
            "round_1": [
                {
                    "agent": "a1",
                    "strategy": "Coop",
                    "score": 3,
                    "belief": {"Coop": 0.5, "Defect": 0.5},
                },
            ],
        }
        rp = ResultsProcessor()
        out = rp._extract_agent_round_data(history, "a1", record_messages=False)
        self.assertEqual(out["beliefs_2nd_order"], [None])
        # Length parity with strategies — preserved positions matter for
        # downstream per-round scoring.
        self.assertEqual(len(out["beliefs_2nd_order"]), len(out["strategies"]))


# ---------------------------------------------------------------------------
# Second-order Brier scoring (soft target = opponent's 1st-order belief)
# ---------------------------------------------------------------------------


class TestSecondOrderBrierMath(unittest.TestCase):
    def test_brier_distribution_matches_classic_when_target_onehot(self) -> None:
        from src.results_processing.belief_metrics import (
            brier_score,
            brier_score_distribution,
        )

        belief = {"strategy1": 0.7, "strategy2": 0.3}
        # One-hot target: opponent assigned 1.0 to strategy1.
        onehot = {"strategy1": 1.0, "strategy2": 0.0}
        self.assertAlmostEqual(
            brier_score_distribution(belief, onehot),
            brier_score(belief, "strategy1"),
            places=9,
        )

    def test_brier_distribution_zero_when_predictions_match(self) -> None:
        from src.results_processing.belief_metrics import brier_score_distribution

        belief = {"strategy1": 0.4, "strategy2": 0.6}
        self.assertAlmostEqual(
            brier_score_distribution(belief, dict(belief)),
            0.0,
            places=9,
        )

    def test_brier_distribution_strict_positive_when_disagreement(self) -> None:
        from src.results_processing.belief_metrics import brier_score_distribution

        a = {"strategy1": 0.9, "strategy2": 0.1}
        b = {"strategy1": 0.1, "strategy2": 0.9}
        score = brier_score_distribution(a, b)
        # Two terms each (0.8)^2 = 0.64 → 1.28.
        self.assertAlmostEqual(score, 1.28, places=6)

    def test_brier_distribution_handles_missing_keys(self) -> None:
        # Defensive: if one side omits a key, treat its probability as 0.
        from src.results_processing.belief_metrics import brier_score_distribution

        a = {"strategy1": 1.0}
        b = {"strategy1": 0.5, "strategy2": 0.5}
        score = brier_score_distribution(a, b)
        # (1.0 - 0.5)^2 + (0.0 - 0.5)^2 = 0.5
        self.assertAlmostEqual(score, 0.5, places=6)

    def test_brier_distribution_missing_key_default_is_zero_not_one(self) -> None:
        # Each side carries a key the other lacks. Asymmetric values (0.4)
        # avoid the squaring symmetry around 0.5 that hides default-value
        # mistakes — under default 0.0 we expect 0.32; under default 1.0
        # on either side the score jumps to 0.52.
        from src.results_processing.belief_metrics import brier_score_distribution

        a = {"strategy2": 0.4}
        b = {"strategy1": 0.4}
        # keys = {s1, s2}; s1: (0-0.4)^2 = 0.16; s2: (0.4-0)^2 = 0.16 → 0.32
        self.assertAlmostEqual(brier_score_distribution(a, b), 0.32, places=6)

    def test_brier_distribution_iterates_union_keys_predicted_side(self) -> None:
        # Mirror case to the missing_keys test above: predicted has a key
        # the target lacks. Iterating only `set(target)` would skip it
        # and underestimate the score.
        from src.results_processing.belief_metrics import brier_score_distribution

        a = {"strategy1": 0.5, "strategy2": 0.5}
        b = {"strategy1": 1.0}
        # strategy1: (0.5-1.0)^2 = 0.25; strategy2: (0.5-0.0)^2 = 0.25 → 0.5
        self.assertAlmostEqual(brier_score_distribution(a, b), 0.5, places=6)


class TestPerRoundSecondOrderMetrics(unittest.TestCase):
    def test_returns_brier_per_round(self) -> None:
        # Per-round second-order metrics: pairs each agent's 2nd-order
        # belief with the opponent's 1st-order belief from the same round.
        from src.results_processing.belief_metrics import per_round_second_order_metrics

        agent_2nd = [
            {"strategy1": 0.7, "strategy2": 0.3},
            {"strategy1": 0.2, "strategy2": 0.8},
            None,  # parse failure
        ]
        opp_1st = [
            {"strategy1": 0.7, "strategy2": 0.3},  # perfect match → brier 0
            {"strategy1": 0.5, "strategy2": 0.5},  # mismatch
            {"strategy1": 1.0, "strategy2": 0.0},  # would score, but agent is None
        ]
        out = per_round_second_order_metrics(agent_2nd, opp_1st)
        self.assertEqual(len(out), 3)
        self.assertAlmostEqual(out[0]["brier"], 0.0, places=6)
        self.assertGreater(out[1]["brier"], 0)
        self.assertIsNone(out[2])

    def test_returns_none_when_either_side_missing(self) -> None:
        from src.results_processing.belief_metrics import per_round_second_order_metrics

        out = per_round_second_order_metrics(
            [{"strategy1": 1.0}],
            [None],
        )
        self.assertEqual(out, [None])

    def test_returns_none_when_either_side_is_empty_dict(self) -> None:
        # Empty dict is just as broken as None — parse_belief returning {}
        # means the LLM gave us nothing usable. Pin the truthy-check semantics
        # so a future refactor to ``is None`` doesn't silently score garbage.
        from src.results_processing.belief_metrics import per_round_second_order_metrics

        out_predicted_empty = per_round_second_order_metrics(
            [{}],
            [{"strategy1": 1.0}],
        )
        self.assertEqual(out_predicted_empty, [None])
        out_target_empty = per_round_second_order_metrics(
            [{"strategy1": 1.0}],
            [{}],
        )
        self.assertEqual(out_target_empty, [None])


# ---------------------------------------------------------------------------
# End-to-end: a full game with elicit_beliefs + tom_order=2 surfaces the
# agentN_belief_2nd_order_* columns in the per-game DataFrame.
# ---------------------------------------------------------------------------


class TestGameDataExposesSecondOrderColumns(unittest.TestCase):
    def test_per_game_row_includes_second_order_brier(self) -> None:
        from src.results_processing.agent_info import AgentInfo
        from src.results_processing.game_data import GameData

        # Two rounds, two agents with both 1st- and 2nd-order beliefs.
        # Mirrors what the engine produces when both phases fire.
        agents = [
            AgentInfo(
                name="agent1",
                llm_service="LLM",
                personality="x",
                opponent_prob=0.0,
            ),
            AgentInfo(
                name="agent2",
                llm_service="LLM",
                personality="y",
                opponent_prob=0.0,
            ),
        ]
        agents_round_data = {
            "agent1": {
                "strategies": ["Coop", "Defect"],
                "scores": [3.0, 5.0],
                "messages": [],
                "beliefs": [
                    {"Coop": 0.5, "Defect": 0.5},
                    {"Coop": 0.4, "Defect": 0.6},
                ],
                "beliefs_2nd_order": [
                    {"Coop": 0.7, "Defect": 0.3},
                    {"Coop": 0.3, "Defect": 0.7},
                ],
            },
            "agent2": {
                "strategies": ["Coop", "Coop"],
                "scores": [3.0, 0.0],
                "messages": [],
                "beliefs": [
                    {"Coop": 0.7, "Defect": 0.3},  # ground truth for agent1's 2nd
                    {"Coop": 0.3, "Defect": 0.7},
                ],
                "beliefs_2nd_order": [
                    {"Coop": 0.6, "Defect": 0.4},
                    {"Coop": 0.4, "Defect": 0.6},
                ],
            },
        }
        matrix_summary = canonical_pd_matrix(labels={"strategy1": "Coop", "strategy2": "Defect"})

        extractor = GameData(
            game_id="g0",
            language="en",
            n_rounds=2,
            n_rounds_is_known=True,
            agents_communicate=False,
            agents=agents,
            agents_round_data=agents_round_data,
            elicit_beliefs=True,
            tom_order=2,
            payoff_matrix_summary=matrix_summary,
            language_for_matrix="en",
        )
        row = extractor.to_dict()

        self.assertIn("agent1_belief_2nd_order_per_round_brier", row)
        self.assertIn("agent2_belief_2nd_order_per_round_brier", row)
        self.assertIn("agent1_belief_2nd_order_mean_brier", row)
        self.assertIn("agent2_belief_2nd_order_mean_brier", row)
        # Round 1: agent1's 2nd-order = {Coop:0.7,Defect:0.3};
        # agent2's 1st-order = {Coop:0.7,Defect:0.3} → identical → Brier 0.
        self.assertAlmostEqual(
            row["agent1_belief_2nd_order_per_round_brier"][0],
            0.0,
            places=6,
        )
        # Round 2: agent1's 2nd-order = {Coop:0.3,Defect:0.7};
        # agent2's 1st-order = {Coop:0.3,Defect:0.7} → also identical → 0.
        self.assertAlmostEqual(
            row["agent1_belief_2nd_order_per_round_brier"][1],
            0.0,
            places=6,
        )
        # Mean over two rounds is the arithmetic mean — pin the value so a
        # mutant that drops the division or swaps sum/len gets caught.
        self.assertAlmostEqual(
            row["agent1_belief_2nd_order_mean_brier"],
            0.0,
            places=6,
        )
        # Agent 2: round 1 2nd-order={Coop:0.6,Defect:0.4} vs agent1's
        # 1st-order={Coop:0.5,Defect:0.5} → (0.1)^2+(0.1)^2 = 0.02. Round 2
        # 2nd-order={Coop:0.4,Defect:0.6} vs agent1.1st={Coop:0.4,Defect:0.6}
        # → 0. Mean = 0.01. Pins the mean math + per-round divisor.
        self.assertAlmostEqual(
            row["agent2_belief_2nd_order_per_round_brier"][0],
            0.02,
            places=6,
        )
        self.assertAlmostEqual(
            row["agent2_belief_2nd_order_per_round_brier"][1],
            0.0,
            places=6,
        )
        self.assertAlmostEqual(
            row["agent2_belief_2nd_order_mean_brier"],
            0.01,
            places=6,
        )

    def test_per_round_brier_records_none_when_predicted_missing(self) -> None:
        # If the agent's 2nd-order belief failed to parse for one round,
        # that slot must be None — not silently elided to a smaller list,
        # not 0.0. A `del`-style mutant on the truthy guard would either
        # crash or produce the wrong shape.
        from src.results_processing.agent_info import AgentInfo
        from src.results_processing.game_data import GameData

        agents = [
            AgentInfo(name="a1", llm_service="L", personality="x", opponent_prob=0.0),
            AgentInfo(name="a2", llm_service="L", personality="y", opponent_prob=0.0),
        ]
        round_data = {
            "a1": {
                "strategies": ["Coop", "Coop"],
                "scores": [0.0, 0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.5, "Defect": 0.5}, {"Coop": 0.5, "Defect": 0.5}],
                "beliefs_2nd_order": [None, {"Coop": 0.5, "Defect": 0.5}],
            },
            "a2": {
                "strategies": ["Coop", "Coop"],
                "scores": [0.0, 0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.5, "Defect": 0.5}, {"Coop": 0.5, "Defect": 0.5}],
                "beliefs_2nd_order": [{"Coop": 0.5, "Defect": 0.5}, None],
            },
        }
        gd = GameData(
            game_id="g0",
            language="en",
            n_rounds=2,
            n_rounds_is_known=True,
            agents_communicate=False,
            agents=agents,
            agents_round_data=round_data,
            elicit_beliefs=True,
            tom_order=2,
        )
        row = gd.to_dict()
        self.assertEqual(len(row["agent1_belief_2nd_order_per_round_brier"]), 2)
        self.assertIsNone(row["agent1_belief_2nd_order_per_round_brier"][0])
        self.assertAlmostEqual(
            row["agent1_belief_2nd_order_per_round_brier"][1],
            0.0,
            places=6,
        )

    def test_per_round_brier_averages_across_multiple_opponents(self) -> None:
        # 3-agent game: agent1 has two opponents per round, so per_round
        # brier is the *mean* of two opponent-side scores. A drop-divisor
        # mutant on `sum(scores) / len(scores)` would emit the sum (twice
        # the mean), so this test pins the inner divisor to len(opponents).
        from src.results_processing.agent_info import AgentInfo
        from src.results_processing.game_data import GameData

        agents = [
            AgentInfo(name="a1", llm_service="L", personality="x", opponent_prob=0.0),
            AgentInfo(name="a2", llm_service="L", personality="y", opponent_prob=0.0),
            AgentInfo(name="a3", llm_service="L", personality="z", opponent_prob=0.0),
        ]
        # a1 predicts {Coop:0.6, Defect:0.4} for what each opponent thinks.
        # a2's actual belief is {Coop:0.6, Defect:0.4} → brier 0.
        # a3's actual belief is {Coop:0.4, Defect:0.6} → brier (0.2)^2*2 = 0.08.
        # Mean over opponents = 0.04. Sum without division would be 0.08.
        round_data = {
            "a1": {
                "strategies": ["Coop"],
                "scores": [0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.5, "Defect": 0.5}],
                "beliefs_2nd_order": [{"Coop": 0.6, "Defect": 0.4}],
            },
            "a2": {
                "strategies": ["Coop"],
                "scores": [0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.6, "Defect": 0.4}],
                "beliefs_2nd_order": [{"Coop": 0.5, "Defect": 0.5}],
            },
            "a3": {
                "strategies": ["Coop"],
                "scores": [0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.4, "Defect": 0.6}],
                "beliefs_2nd_order": [{"Coop": 0.5, "Defect": 0.5}],
            },
        }
        gd = GameData(
            game_id="g0",
            language="en",
            n_rounds=1,
            n_rounds_is_known=True,
            agents_communicate=False,
            agents=agents,
            agents_round_data=round_data,
            elicit_beliefs=True,
            tom_order=2,
        )
        row = gd.to_dict()
        self.assertAlmostEqual(
            row["agent1_belief_2nd_order_per_round_brier"][0],
            0.04,
            places=6,
        )

    def test_per_round_brier_skips_rounds_where_opponent_belief_missing(self) -> None:
        # Game stopped early for the opponent: opp.beliefs is shorter than
        # this agent's beliefs_2nd_order. Round-index guard must skip those
        # rounds (None in per_round) instead of IndexError.
        from src.results_processing.agent_info import AgentInfo
        from src.results_processing.game_data import GameData

        agents = [
            AgentInfo(name="a1", llm_service="L", personality="x", opponent_prob=0.0),
            AgentInfo(name="a2", llm_service="L", personality="y", opponent_prob=0.0),
        ]
        round_data = {
            "a1": {
                "strategies": ["Coop", "Coop"],
                "scores": [0.0, 0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.5, "Defect": 0.5}],  # only round 0
                "beliefs_2nd_order": [
                    {"Coop": 0.5, "Defect": 0.5},
                    {"Coop": 0.5, "Defect": 0.5},
                ],
            },
            "a2": {
                "strategies": ["Coop", "Coop"],
                "scores": [0.0, 0.0],
                "messages": [],
                "beliefs": [{"Coop": 0.5, "Defect": 0.5}],  # only round 0
                "beliefs_2nd_order": [
                    {"Coop": 0.5, "Defect": 0.5},
                    {"Coop": 0.5, "Defect": 0.5},
                ],
            },
        }
        gd = GameData(
            game_id="g0",
            language="en",
            n_rounds=2,
            n_rounds_is_known=True,
            agents_communicate=False,
            agents=agents,
            agents_round_data=round_data,
            elicit_beliefs=True,
            tom_order=2,
        )
        row = gd.to_dict()
        # Round 0 has data → 0.0; round 1 has no opponent belief → None.
        self.assertAlmostEqual(
            row["agent1_belief_2nd_order_per_round_brier"][0],
            0.0,
            places=6,
        )
        self.assertIsNone(row["agent1_belief_2nd_order_per_round_brier"][1])


if __name__ == "__main__":
    unittest.main()
