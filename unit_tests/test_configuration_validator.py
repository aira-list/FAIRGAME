"""Tests for :class:`src.io_managers.configuration_validator.ConfigValidator`."""

from __future__ import annotations

import copy
import unittest

from src.io_managers.configuration_validator import ConfigValidator

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _base_config() -> dict:
    return {
        "name": "Demo",
        "nRounds": 1,
        "nRoundsIsKnown": True,
        "llm": "OpenAIGPT4o",
        "languages": ["en"],
        "allAgentPermutations": True,
        "agents": {
            "names": ["a1", "a2"],
            "personalities": {"en": ["nice", "mean"]},
            "opponentPersonalityProb": [0],
        },
        "payoffMatrix": {
            "weights": {"w1": 1, "w2": 2},
            "strategies": {"en": {"strategy1": "X", "strategy2": "Y"}},
            "combinations": {
                "c1": ["strategy1", "strategy1"],
                "c2": ["strategy2", "strategy2"],
            },
            "matrix": {"c1": ["w1", "w1"], "c2": ["w2", "w2"]},
        },
        "stopGameWhen": ["c1"],
        "agentsCommunicate": False,
        "templateFilename": "demo",
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_well_formed_config_returns_dict(self) -> None:
        result = self.validator.validate_config_structure(_base_config())
        self.assertEqual(result["name"], "Demo")
        self.assertEqual(result["agents"]["names"], ["a1", "a2"])

    def test_default_optional_fields_appear_with_defaults(self) -> None:
        result = self.validator.validate_config_structure(_base_config())
        self.assertEqual(result.get("elicitBeliefs"), False)
        self.assertEqual(result.get("tomOrder"), 1)
        self.assertEqual(result.get("discountFactor"), 1.0)
        self.assertEqual(result.get("mixedStrategies"), False)
        self.assertEqual(result.get("equilibria"), [])

    def test_all_agent_permutations_defaults_to_false_when_omitted(self) -> None:
        """Stored library configs predating this field must still validate.
        Reason: data/configurations.json on installs older than 2026-05-16
        is missing this key for the first seeded entry."""
        config = _base_config()
        del config["allAgentPermutations"]
        # When allAgentPermutations is False, opponentPersonalityProb is a
        # 1:1 list with agents, not a permutation pool.
        config["agents"]["opponentPersonalityProb"] = [0, 0]
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result.get("allAgentPermutations"), False)

    def test_stop_game_when_defaults_to_empty_list_when_omitted(self) -> None:
        """Missing ``stopGameWhen`` means no early-stop conditions — safer
        than rejecting the config outright."""
        config = _base_config()
        del config["stopGameWhen"]
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result.get("stopGameWhen"), [])

    def test_input_dict_is_not_mutated(self) -> None:
        config = _base_config()
        snapshot = copy.deepcopy(config)
        self.validator.validate_config_structure(config)
        self.assertEqual(config, snapshot)


# ---------------------------------------------------------------------------
# Template binding (mutual exclusivity)
# ---------------------------------------------------------------------------


class TestTemplateBinding(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_both_sources_rejected(self) -> None:
        config = _base_config()
        config["promptTemplate"] = {"en": "..."}
        with self.assertRaises(TypeError) as ctx:
            self.validator.validate_config_structure(config)
        self.assertIn("Exactly one of", str(ctx.exception))

    def test_missing_both_sources_rejected(self) -> None:
        config = _base_config()
        del config["templateFilename"]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_only_prompt_template_accepted(self) -> None:
        config = _base_config()
        del config["templateFilename"]
        config["promptTemplate"] = {"en": "{currentPlayerName} {choose}: [Pick]"}
        result = self.validator.validate_config_structure(config)
        self.assertIn("promptTemplate", result)


# ---------------------------------------------------------------------------
# LLM resolution
# ---------------------------------------------------------------------------


class TestLLMResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_llm_and_llms_both_set_rejected(self) -> None:
        config = _base_config()
        config["llms"] = {"a1": "OpenAIGPT4o", "a2": "OpenAIGPT4o"}
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_neither_llm_nor_llms_rejected(self) -> None:
        config = _base_config()
        del config["llm"]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_llms_list_length_must_match_agents(self) -> None:
        config = _base_config()
        del config["llm"]
        config["llms"] = ["OpenAIGPT4o"]  # one entry for two agents
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_llms_dict_must_match_agent_names_exactly(self) -> None:
        config = _base_config()
        del config["llm"]
        config["llms"] = {"a1": "OpenAIGPT4o"}  # missing a2
        with self.assertRaises(TypeError) as ctx:
            self.validator.validate_config_structure(config)
        self.assertIn("a2", str(ctx.exception))

    def test_llms_dict_with_extra_keys_rejected(self) -> None:
        config = _base_config()
        del config["llm"]
        config["llms"] = {"a1": "x", "a2": "x", "extra": "x"}
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_llms_with_empty_string_values_rejected(self) -> None:
        config = _base_config()
        del config["llm"]
        config["llms"] = {"a1": "", "a2": "x"}
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)


# ---------------------------------------------------------------------------
# Personality / probability validation
# ---------------------------------------------------------------------------


class TestPersonalityValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_strict_mode_requires_one_personality_per_agent(self) -> None:
        config = _base_config()
        config["allAgentPermutations"] = False
        config["agents"]["opponentPersonalityProb"] = [0, 0]
        config["agents"]["personalities"]["en"] = ["only-one"]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_permutation_mode_treats_personalities_as_pool(self) -> None:
        # In permutation mode, len(personalities) need not equal len(agents).
        config = _base_config()
        config["allAgentPermutations"] = True
        config["agents"]["personalities"]["en"] = ["pool-of-one"]
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["agents"]["personalities"]["en"], ["pool-of-one"])

    def test_empty_personality_pool_rejected(self) -> None:
        config = _base_config()
        config["allAgentPermutations"] = True
        config["agents"]["personalities"]["en"] = []
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_strict_mode_requires_opponent_prob_per_agent(self) -> None:
        config = _base_config()
        config["allAgentPermutations"] = False
        # personalities matched, but opp prob list short.
        config["agents"]["personalities"]["en"] = ["a", "b"]
        config["agents"]["opponentPersonalityProb"] = [0]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_permutation_mode_requires_non_empty_opp_prob_list(self) -> None:
        config = _base_config()
        config["allAgentPermutations"] = True
        config["agents"]["opponentPersonalityProb"] = []
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_fewer_than_two_agents_rejected(self) -> None:
        config = _base_config()
        config["agents"]["names"] = ["only_one"]
        config["agents"]["personalities"]["en"] = ["lonely"]
        config["agents"]["opponentPersonalityProb"] = [0]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)


# ---------------------------------------------------------------------------
# Fake communication
# ---------------------------------------------------------------------------


class TestFakeCommunication(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_invalid_base_rejected(self) -> None:
        config = _base_config()
        config["fakeCommunication"] = True
        config["fakeMessageBase"] = "octal"
        with self.assertRaises(TypeError) as ctx:
            self.validator.validate_config_structure(config)
        self.assertIn("dec", str(ctx.exception).lower())

    def test_zero_message_count_rejected(self) -> None:
        config = _base_config()
        config["fakeCommunication"] = True
        config["fakeMessageCount"] = 0
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_negative_message_count_rejected(self) -> None:
        config = _base_config()
        config["fakeCommunication"] = True
        config["fakeMessageCount"] = -1
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_disabled_fake_communication_doesnt_validate_base(self) -> None:
        # Fake communication off → base is irrelevant, even if "octal".
        config = _base_config()
        config["fakeCommunication"] = False
        config["fakeMessageBase"] = "octal"
        # Should not raise.
        result = self.validator.validate_config_structure(config)
        self.assertFalse(result["fakeCommunication"])


# ---------------------------------------------------------------------------
# Game-theory extensions
# ---------------------------------------------------------------------------


class TestGameTheoryExtensions(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_discount_factor_zero_rejected(self) -> None:
        config = _base_config()
        config["discountFactor"] = 0.0
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_discount_factor_above_one_rejected(self) -> None:
        config = _base_config()
        config["discountFactor"] = 1.5
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_discount_factor_one_accepted(self) -> None:
        config = _base_config()
        config["discountFactor"] = 1.0
        # Should not raise.
        self.validator.validate_config_structure(config)

    def test_continuation_probability_zero_rejected(self) -> None:
        config = _base_config()
        config["continuationProbability"] = 0.0
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_continuation_probability_above_one_rejected(self) -> None:
        config = _base_config()
        config["continuationProbability"] = 1.5
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_seed_count_zero_rejected(self) -> None:
        config = _base_config()
        config["seedCount"] = 0
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_seeds_must_be_list_of_ints(self) -> None:
        config = _base_config()
        config["seeds"] = ["not-an-int"]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_equilibria_auto_string_passes_validation(self) -> None:
        config = _base_config()
        config["equilibria"] = "auto"
        # Should not raise — handled in the validator.
        result = self.validator.validate_config_structure(config)
        # After resolution it's a list (possibly empty for this minimal matrix).
        self.assertIsInstance(result["equilibria"], list)

    def test_equilibria_explicit_list_left_alone(self) -> None:
        config = _base_config()
        config["equilibria"] = ["c1", "c2"]
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["equilibria"], ["c1", "c2"])


# ---------------------------------------------------------------------------
# Payoff matrix transformation
# ---------------------------------------------------------------------------


class TestPayoffMatrixTransformation(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_legacy_pair_format_is_transformed(self) -> None:
        config = _base_config()
        config["payoffMatrix"]["combinations"] = {
            "c1": [["strategy1", "w1"], ["strategy1", "w1"]],
            "c2": [["strategy2", "w2"], ["strategy2", "w2"]],
        }
        del config["payoffMatrix"]["matrix"]
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["payoffMatrix"]["matrix"]["c1"], ["w1", "w1"])
        self.assertEqual(
            result["payoffMatrix"]["combinations"]["c1"],
            ["strategy1", "strategy1"],
        )

    def test_canonical_format_passes_through_unchanged(self) -> None:
        before = _base_config()
        result = self.validator.validate_config_structure(before)
        # Round-trip: combinations/matrix are unchanged.
        self.assertEqual(
            result["payoffMatrix"]["combinations"], before["payoffMatrix"]["combinations"]
        )
        self.assertEqual(result["payoffMatrix"]["matrix"], before["payoffMatrix"]["matrix"])


class TestCombinationKeyReferences(unittest.TestCase):
    """``stopGameWhen`` / explicit ``equilibria`` entries must name real
    combinations — a typo silently disabled the stop rule (games ran the
    full horizon) or zeroed the equilibrium_rate."""

    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_unknown_stop_condition_rejected(self) -> None:
        config = _base_config()
        config["stopGameWhen"] = ["c_1"]  # typo: real keys are c1/c2
        with self.assertRaises(ValueError) as ctx:
            self.validator.validate_config_structure(config)
        self.assertIn("stopGameWhen", str(ctx.exception))
        self.assertIn("c_1", str(ctx.exception))

    def test_unknown_explicit_equilibrium_rejected(self) -> None:
        config = _base_config()
        config["equilibria"] = ["c1", "combination9"]
        with self.assertRaises(ValueError) as ctx:
            self.validator.validate_config_structure(config)
        self.assertIn("equilibria", str(ctx.exception))

    def test_known_keys_accepted(self) -> None:
        config = _base_config()
        config["stopGameWhen"] = ["c1", "c2"]
        config["equilibria"] = ["c2"]
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["stopGameWhen"], ["c1", "c2"])


class TestOpponentProbScaleNudge(unittest.TestCase):
    """opponentPersonalityProb is rendered verbatim into '...{value}%', so a
    0-1-scale value is almost certainly a mixup ("0.7%" instead of "70%").
    Accepted for backwards compatibility, but must warn loudly."""

    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_fractional_prob_warns(self) -> None:
        config = _base_config()
        config["allAgentPermutations"] = False
        config["agents"]["opponentPersonalityProb"] = [0.7, 0.7]
        with self.assertLogs("src.io_managers.configuration_validator", level="WARNING") as logs:
            self.validator.validate_config_structure(config)
        self.assertTrue(any("0.7" in line and "%" in line for line in logs.output))

    def test_percent_probs_do_not_warn(self) -> None:
        import logging

        config = _base_config()
        config["allAgentPermutations"] = False
        config["agents"]["opponentPersonalityProb"] = [0, 70]
        logger = logging.getLogger("src.io_managers.configuration_validator")
        records: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = records.append  # type: ignore[assignment]
        logger.addHandler(handler)
        try:
            self.validator.validate_config_structure(config)
        finally:
            logger.removeHandler(handler)
        self.assertFalse([r for r in records if r.levelno >= logging.WARNING])


if __name__ == "__main__":
    unittest.main()
