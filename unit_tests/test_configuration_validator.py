"""Tests for :class:`src.io_managers.configuration_validator.ConfigValidator`."""

from __future__ import annotations

import copy
import unittest

from src.io_managers.configuration_validator import ConfigValidator


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


class TestConfigValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_well_formed_config_returns_dump(self) -> None:
        config = _base_config()
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["name"], "Demo")
        self.assertEqual(result["agents"]["names"], ["a1", "a2"])

    def test_both_template_sources_rejected(self) -> None:
        config = _base_config()
        config["promptTemplate"] = {"en": "..."}
        # templateFilename is already set, so both are present -> invalid.
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_missing_template_sources_rejected(self) -> None:
        config = _base_config()
        del config["templateFilename"]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_llm_and_llms_both_set_rejected(self) -> None:
        config = _base_config()
        config["llms"] = {"a1": "OpenAIGPT4o", "a2": "OpenAIGPT4o"}
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_llms_dict_keys_must_match_agents(self) -> None:
        config = _base_config()
        del config["llm"]
        config["llms"] = {"a1": "OpenAIGPT4o"}  # missing a2
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_personalities_count_must_match_agents_in_strict_mode(self) -> None:
        # When ``allAgentPermutations=False`` personalities is 1:1 with agents.
        config = _base_config()
        config["allAgentPermutations"] = False
        config["agents"]["opponentPersonalityProb"] = [0, 0]
        config["agents"]["personalities"]["en"] = ["only-one"]
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_personality_pool_sized_freely_in_permutation_mode(self) -> None:
        # In permutation mode the entries are a value pool, not a 1:1 list.
        config = _base_config()
        config["allAgentPermutations"] = True
        config["agents"]["personalities"]["en"] = ["only-one"]
        # Should not raise.
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["agents"]["personalities"]["en"], ["only-one"])

    def test_empty_personality_pool_rejected(self) -> None:
        config = _base_config()
        config["allAgentPermutations"] = True
        config["agents"]["personalities"]["en"] = []
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_fake_communication_requires_valid_base(self) -> None:
        config = _base_config()
        config["fakeCommunication"] = True
        config["fakeMessageBase"] = "octal"
        with self.assertRaises(TypeError):
            self.validator.validate_config_structure(config)

    def test_legacy_pair_payoff_matrix_is_transformed(self) -> None:
        config = _base_config()
        config["payoffMatrix"]["combinations"] = {
            "c1": [["strategy1", "w1"], ["strategy1", "w1"]],
            "c2": [["strategy2", "w2"], ["strategy2", "w2"]],
        }
        del config["payoffMatrix"]["matrix"]
        result = self.validator.validate_config_structure(config)
        # Transformer rebuilt the matrix block from the [strategy, weight] pairs.
        self.assertEqual(result["payoffMatrix"]["matrix"]["c1"], ["w1", "w1"])
        self.assertEqual(result["payoffMatrix"]["combinations"]["c1"], ["strategy1", "strategy1"])

    def test_immutability_of_input(self) -> None:
        config = _base_config()
        snapshot = copy.deepcopy(config)
        self.validator.validate_config_structure(config)
        self.assertEqual(config, snapshot, "validator should not mutate caller's dict")


if __name__ == "__main__":
    unittest.main()
