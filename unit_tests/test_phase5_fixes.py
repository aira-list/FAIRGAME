"""Phase 5 — data/stats correctness + robustness regression tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from src.results_processing.belief_metrics import brier_score
from src.results_processing.seed_aggregator import _normal_inverse, aggregate_seeds
from src.utility import build_utility_transform
from src.utils.utils import get_project_root


class TestBrierValidation(unittest.TestCase):
    def test_accepts_normalised(self) -> None:
        self.assertAlmostEqual(brier_score({"a": 0.7, "b": 0.3}, "a"), 0.18)

    def test_rejects_unnormalised_logits(self) -> None:
        with self.assertRaises(ValueError):
            brier_score({"a": 3.0, "b": 2.0}, "a")  # raw logits, sum != 1

    def test_rejects_negative_prob(self) -> None:
        with self.assertRaises(ValueError):
            brier_score({"a": 1.5, "b": -0.5}, "a")


class TestNormalInverseTailAccuracy(unittest.TestCase):
    def test_matches_reference_for_non_95(self) -> None:
        # The tail branch (confidence > ~0.85) used to be materially wrong.
        # 99% two-sided critical value is 2.5758.
        self.assertAlmostEqual(_normal_inverse(0.99), 2.5758293, places=4)

    def test_matches_reference_for_999(self) -> None:
        self.assertAlmostEqual(_normal_inverse(0.999), 3.2905267, places=4)


class TestSeedAggregatorConstantBoolean(unittest.TestCase):
    def test_constant_bool_preserved_not_averaged(self) -> None:
        df = pd.DataFrame(
            {
                "language": ["en", "en"],
                "seed": [1, 2],
                "n_rounds_is_known": [True, True],
                "welfare_sum": [10.0, 12.0],
            }
        )
        out = aggregate_seeds(df, grouping_columns=["language"])
        row = out.iloc[0]
        # Boolean flag preserved as-is, NOT coerced to a 0/1 mean.
        self.assertIn("n_rounds_is_known", out.columns)
        self.assertEqual(row["n_rounds_is_known"], True)
        self.assertNotIn("n_rounds_is_known_mean", out.columns)
        # Genuine numeric metric still aggregated.
        self.assertIn("welfare_sum_mean", out.columns)
        self.assertAlmostEqual(row["welfare_sum_mean"], 11.0)


class TestUtilsLevelsUp(unittest.TestCase):
    def test_overcount_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_project_root(Path("/a/b"), 99)

    def test_negative_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_project_root(Path("/a/b"), -1)

    def test_normal_walk(self) -> None:
        self.assertEqual(get_project_root(Path("/a/b/c"), 2), Path("/a"))


class TestBuildUtilityTransform(unittest.TestCase):
    def test_misspelled_key_raises_clear_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_utility_transform({"type": "CRRA", "gammma": 0.5})  # typo
        self.assertIn("gammma", str(ctx.exception))

    def test_valid_config_ok(self) -> None:
        t = build_utility_transform({"type": "CRRA", "gamma": 0.5})
        self.assertIsNotNone(t)


class TestTemplatePlaceholderOrder(unittest.TestCase):
    def test_reordered_placeholders_accepted(self) -> None:
        from src.template_translation.template_translator import TemplateTranslator

        tr = TemplateTranslator("fake")
        # Same placeholders, different order — must NOT raise.
        tr.check_all_placeholders_preserved("a {x} b {y}", "d {y} c {x}")

    def test_missing_placeholder_still_rejected(self) -> None:
        from src.template_translation.template_translator import TemplateTranslator

        tr = TemplateTranslator("fake")
        with self.assertRaises(ValueError):
            tr.check_all_placeholders_preserved("a {x} b {y}", "a {x}")


if __name__ == "__main__":
    unittest.main()
