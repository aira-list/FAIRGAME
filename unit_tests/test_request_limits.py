"""Security regression tests: request size/range caps + rate-file path.

These never invoke the engine or load any model — they assert validation
rejects abusive inputs before the handler runs.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from src.llm_connectors.abstract_connector import _default_rate_file
from web_api.models import (
    MAX_RUN_ITERATIONS,
    RunConfigurationsBody,
)


class TestRunIterationsBound(unittest.TestCase):
    def test_default_is_one(self) -> None:
        self.assertEqual(RunConfigurationsBody(configuration_ids=["a"]).iterations, 1)

    def test_over_max_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RunConfigurationsBody(configuration_ids=["a"], iterations=MAX_RUN_ITERATIONS + 1)

    def test_zero_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RunConfigurationsBody(configuration_ids=["a"], iterations=0)


class TestRateFileDefault(unittest.TestCase):
    def test_default_rate_file_is_per_user(self) -> None:
        path = _default_rate_file()
        # No longer the fixed, world-predictable shared name.
        self.assertNotEqual(path, "/tmp/fairgame_llm_rate.bucket")
        self.assertIn("fairgame_llm_rate_", path)


if __name__ == "__main__":
    unittest.main()
