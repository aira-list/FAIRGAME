"""payoffDirection semantics + the validator guards added alongside it.

``payoffDirection: "penalty"`` declares that the matrix weights are costs
(lower is better). The prompt always renders the raw numbers; the analytic
layer — auto equilibria, best-response regret, welfare efficiency — must
flip direction, otherwise a penalty-framed game is scored as its own
inverse (the defect action of the described game gets counted as
cooperation-side equilibrium play and vice versa).
"""

from __future__ import annotations

import unittest

from src.game.game_config import GameConfig
from src.game_theory.equilibrium import compute_nash_equilibria
from src.io_managers.configuration_validator import ConfigValidator
from src.results_processing.belief_metrics import belief_agreement
from src.results_processing.game_metrics import welfare_summary
from src.results_processing.regret import best_response_payoff, regret_per_round

# The shipped PD numbers: as rewards, T=10 > R=6 > P=2 > S=0 with the unique
# pure NE at mutual strategy2; as penalties the same numbers are the swapped
# PD whose unique pure NE is mutual strategy1.
PD_MATRIX = {
    "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
    "strategies": {"en": {"strategy1": "OptionA", "strategy2": "OptionB"}},
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


def _base_config(**over):
    cfg = {
        "name": "direction-test",
        "nRounds": 2,
        "nRoundsIsKnown": True,
        "payoffMatrix": {k: (dict(v) if isinstance(v, dict) else v) for k, v in PD_MATRIX.items()},
        "agents": {
            "names": ["agent1", "agent2"],
            "personalities": {"en": ["neutral", "neutral"]},
            "opponentPersonalityProb": [0, 0],
        },
        "llm": "GPT-4o",
        "languages": ["en"],
        "agentsCommunicate": False,
        "promptTemplate": {"en": "Choose between {strategy1} and {strategy2}."},
    }
    cfg.update(over)
    return cfg


class TestAutoEquilibriaDirection(unittest.TestCase):
    def test_reward_direction_finds_mutual_defection(self) -> None:
        self.assertEqual(compute_nash_equilibria(PD_MATRIX, "en"), ["combination4"])
        self.assertEqual(
            compute_nash_equilibria(PD_MATRIX, "en", direction="reward"), ["combination4"]
        )

    def test_penalty_direction_finds_the_swapped_equilibrium(self) -> None:
        self.assertEqual(
            compute_nash_equilibria(PD_MATRIX, "en", direction="penalty"), ["combination1"]
        )

    def test_validator_threads_direction_into_auto(self) -> None:
        result = ConfigValidator().validate_config_structure(
            _base_config(equilibria="auto", payoffDirection="penalty")
        )
        self.assertEqual(result["equilibria"], ["combination1"])
        result = ConfigValidator().validate_config_structure(_base_config(equilibria="auto"))
        self.assertEqual(result["equilibria"], ["combination4"])


class TestRegretDirection(unittest.TestCase):
    def test_penalty_best_response_is_the_minimum(self) -> None:
        # Opponent played OptionA. Reward: best = 10 (defect). Penalty:
        # best = 6 (the cheaper of {6, 10}).
        self.assertEqual(best_response_payoff(PD_MATRIX, "en", 0, ["OptionA"]), 10.0)
        self.assertEqual(
            best_response_payoff(PD_MATRIX, "en", 0, ["OptionA"], direction="penalty"), 6.0
        )

    def test_penalty_regret_is_excess_cost(self) -> None:
        # Agent 0 played OptionB against OptionA (combination3): its own
        # weight is 10. Under the penalty reading the cheapest reply was
        # OptionA at cost 6, so it overpaid by 4.
        regret = regret_per_round(
            PD_MATRIX, "en", 0, ["OptionB"], [["OptionA"]], direction="penalty"
        )
        self.assertEqual(regret, [4.0])
        # The reward reading of the same round has zero regret (10 was best).
        regret = regret_per_round(PD_MATRIX, "en", 0, ["OptionB"], [["OptionA"]])
        self.assertEqual(regret, [0.0])


class TestWelfareEfficiencyDirection(unittest.TestCase):
    def test_penalty_efficiency_inverts_the_ratio(self) -> None:
        scores = {"a": [4.0], "b": [4.0]}  # round sum 8
        # Reward: 8 achieved / 12 achievable.
        out = welfare_summary(scores, pareto_optimal_sum=12)
        self.assertAlmostEqual(out["welfare_efficiency"], 8 / 12)
        # Penalty: 4 achievable (lowest cost sum) / 8 paid.
        out = welfare_summary(scores, pareto_optimal_sum=4, direction="penalty")
        self.assertAlmostEqual(out["welfare_efficiency"], 4 / 8)


class TestGameConfigField(unittest.TestCase):
    def test_default_is_reward_and_lands_in_description(self) -> None:
        cfg = GameConfig.from_raw(
            {
                "name": "g",
                "nRounds": 1,
                "nRoundsIsKnown": True,
                "agentsCommunicate": False,
                "stopGameWhen": [],
            },
            language="en",
            payoff_matrix_data=PD_MATRIX,
            prompt_template="x",
            types_config=None,
            rng=None,
            seed=None,
        )
        self.assertEqual(cfg.payoff_direction, "reward")
        self.assertEqual(cfg.to_description()["payoff_direction"], "reward")

    def test_penalty_round_trips_and_bad_value_raises(self) -> None:
        raw = {
            "name": "g",
            "nRounds": 1,
            "nRoundsIsKnown": True,
            "agentsCommunicate": False,
            "stopGameWhen": [],
            "payoffDirection": "penalty",
        }
        cfg = GameConfig.from_raw(
            raw,
            language="en",
            payoff_matrix_data=PD_MATRIX,
            prompt_template="x",
            types_config=None,
            rng=None,
            seed=None,
        )
        self.assertEqual(cfg.to_description()["payoff_direction"], "penalty")
        raw["payoffDirection"] = "maximize"
        with self.assertRaises(ValueError):
            GameConfig.from_raw(
                raw,
                language="en",
                payoff_matrix_data=PD_MATRIX,
                prompt_template="x",
                types_config=None,
                rng=None,
                seed=None,
            )

    def test_validator_rejects_unknown_direction(self) -> None:
        with self.assertRaises(TypeError):
            ConfigValidator().validate_config_structure(_base_config(payoffDirection="maximize"))


class TestValidatorGuards(unittest.TestCase):
    def test_equilibria_plain_string_is_rejected(self) -> None:
        # Anything but "auto" as a string used to be silently list()-split
        # into characters, zeroing equilibrium_rate.
        with self.assertRaises(TypeError):
            ConfigValidator().validate_config_structure(_base_config(equilibria="combination4"))

    def test_language_missing_from_personalities_is_rejected(self) -> None:
        cfg = _base_config(languages=["en", "fr"])
        cfg["promptTemplate"]["fr"] = "Choisissez."
        cfg["payoffMatrix"]["strategies"] = {
            "en": {"strategy1": "OptionA", "strategy2": "OptionB"},
            "fr": {"strategy1": "OptionA", "strategy2": "OptionB"},
        }
        with self.assertRaises(TypeError):
            ConfigValidator().validate_config_structure(cfg)

    def test_language_missing_from_prompt_template_is_rejected(self) -> None:
        cfg = _base_config(languages=["en", "fr"])
        cfg["agents"]["personalities"]["fr"] = ["neutre", "neutre"]
        cfg["payoffMatrix"]["strategies"] = {
            "en": {"strategy1": "OptionA", "strategy2": "OptionB"},
            "fr": {"strategy1": "OptionA", "strategy2": "OptionB"},
        }
        with self.assertRaises(TypeError):
            ConfigValidator().validate_config_structure(cfg)

    def test_matrix_referencing_undefined_weight_is_rejected(self) -> None:
        cfg = _base_config()
        cfg["payoffMatrix"] = {
            **{k: (dict(v) if isinstance(v, dict) else v) for k, v in PD_MATRIX.items()},
            "matrix": {**PD_MATRIX["matrix"], "combination4": ["weight4", "weight5"]},
        }
        with self.assertRaises(ValueError):
            ConfigValidator().validate_config_structure(cfg)

    def test_matrix_and_combinations_must_share_keys(self) -> None:
        cfg = _base_config()
        matrix = dict(PD_MATRIX["matrix"])
        del matrix["combination4"]
        cfg["payoffMatrix"] = {
            **{k: (dict(v) if isinstance(v, dict) else v) for k, v in PD_MATRIX.items()},
            "matrix": matrix,
        }
        with self.assertRaises((ValueError, KeyError)):
            ConfigValidator().validate_config_structure(cfg)

    def test_canonical_matrix_missing_matrix_block_fails_loudly(self) -> None:
        # Used to get "transformed" by slicing strategy-key strings into
        # characters, then accepted — crashing mid-game instead of here.
        cfg = _base_config()
        pm = {k: (dict(v) if isinstance(v, dict) else v) for k, v in PD_MATRIX.items()}
        del pm["matrix"]
        cfg["payoffMatrix"] = pm
        with self.assertRaises((KeyError, ValueError)):
            ConfigValidator().validate_config_structure(cfg)


class TestBeliefAgreementTies(unittest.TestCase):
    def test_tie_is_never_agreement(self) -> None:
        belief = {"strategy1": 0.5, "strategy2": 0.5}
        self.assertFalse(belief_agreement(belief, "strategy1"))
        self.assertFalse(belief_agreement(belief, "strategy2"))
        self.assertTrue(belief_agreement({"strategy1": 0.6, "strategy2": 0.4}, "strategy1"))


if __name__ == "__main__":
    unittest.main()
