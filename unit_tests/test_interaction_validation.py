"""Validation of the optional ``interaction`` config block.

The block must survive ``model_dump`` (so the factory can build the graph)
and bad edges must fail at config-validation time rather than deep in the
engine.
"""

from __future__ import annotations

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


class TestInteractionValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConfigValidator()

    def test_absent_block_is_fine(self) -> None:
        result = self.validator.validate_config_structure(_base_config())
        self.assertIsNone(result.get("interaction"))

    def test_valid_block_survives_model_dump(self) -> None:
        config = _base_config()
        config["interaction"] = {
            "directed": True,
            "default": "see",
            "edges": [{"from": "a1", "to": "a2", "level": "talk"}],
        }
        result = self.validator.validate_config_structure(config)
        self.assertEqual(result["interaction"]["default"], "see")
        self.assertEqual(result["interaction"]["edges"][0]["level"], "talk")

    def test_unknown_endpoint_rejected(self) -> None:
        config = _base_config()
        config["interaction"] = {"edges": [{"from": "a1", "to": "ghost", "level": "talk"}]}
        with self.assertRaises((TypeError, ValueError)):
            self.validator.validate_config_structure(config)

    def test_bad_level_rejected(self) -> None:
        config = _base_config()
        config["interaction"] = {"edges": [{"from": "a1", "to": "a2", "level": "whisper"}]}
        with self.assertRaises((TypeError, ValueError)):
            self.validator.validate_config_structure(config)

    def test_bad_default_rejected(self) -> None:
        config = _base_config()
        config["interaction"] = {"default": "whisper"}
        with self.assertRaises((TypeError, ValueError)):
            self.validator.validate_config_structure(config)

    def test_edge_missing_endpoint_key_rejected(self) -> None:
        config = _base_config()
        config["interaction"] = {"edges": [{"from": "a1", "level": "talk"}]}
        with self.assertRaises((TypeError, ValueError)):
            self.validator.validate_config_structure(config)


if __name__ == "__main__":
    unittest.main()
