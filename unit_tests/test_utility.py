"""Tests for :mod:`src.utility`."""

from __future__ import annotations

import math
import unittest

from src.utility import (
    CRRATransform,
    FehrSchmidtTransform,
    IdentityTransform,
    build_utility_transform,
)


class TestIdentityTransform(unittest.TestCase):
    def test_identity_is_a_no_op(self) -> None:
        self.assertEqual(IdentityTransform().transform([1, 2, 3]), [1, 2, 3])


class TestCRRATransform(unittest.TestCase):
    def test_log_case_when_gamma_one(self) -> None:
        result = CRRATransform(gamma=1.0).transform([math.e - 1])  # offset=1 by default
        self.assertAlmostEqual(result[0], math.log(math.e), places=5)

    def test_risk_neutral_at_gamma_zero_is_affine(self) -> None:
        # γ=0 collapses to (x + offset) - 1: a strictly increasing affine map
        # of the raw payoff. Check ordering is preserved.
        u = CRRATransform(gamma=0.0, offset=1.0).transform([1.0, 2.0, 3.0])
        self.assertEqual(u, sorted(u))

    def test_higher_gamma_is_more_risk_averse(self) -> None:
        risk_neutral = CRRATransform(gamma=0.0).transform([1.0, 5.0])
        risk_averse = CRRATransform(gamma=0.8).transform([1.0, 5.0])
        # Mean is preserved by the offset+1 in risk_neutral and shrunk by risk-aversion.
        self.assertGreater(risk_neutral[1] - risk_neutral[0], risk_averse[1] - risk_averse[0])

    def test_negative_gamma_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CRRATransform(gamma=-0.1)

    def test_non_positive_shifted_payoff_raises(self) -> None:
        with self.assertRaises(ValueError):
            CRRATransform(gamma=0.5, offset=0.0).transform([0.0])


class TestFehrSchmidtTransform(unittest.TestCase):
    def test_equal_payoffs_unchanged(self) -> None:
        u = FehrSchmidtTransform(alpha=0.5, beta=0.5).transform([1.0, 1.0, 1.0])
        self.assertEqual(u, [1.0, 1.0, 1.0])

    def test_envy_is_costly(self) -> None:
        # Agent 0 has lower payoff -> envy reduces u_0 below x_0.
        u = FehrSchmidtTransform(alpha=0.5, beta=0.0).transform([0.0, 4.0])
        self.assertLess(u[0], 0.0)

    def test_guilt_is_costly(self) -> None:
        u = FehrSchmidtTransform(alpha=0.0, beta=0.5).transform([4.0, 0.0])
        self.assertLess(u[0], 4.0)

    def test_negative_alpha_or_beta_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FehrSchmidtTransform(alpha=-0.1, beta=0.0)
        with self.assertRaises(ValueError):
            FehrSchmidtTransform(alpha=0.0, beta=-0.1)


class TestBuildUtilityTransform(unittest.TestCase):
    def test_none_returns_identity(self) -> None:
        self.assertIsInstance(build_utility_transform(None), IdentityTransform)

    def test_unknown_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_utility_transform({"type": "Bogus"})

    def test_builds_crra(self) -> None:
        t = build_utility_transform({"type": "CRRA", "gamma": 0.5})
        self.assertIsInstance(t, CRRATransform)
        self.assertAlmostEqual(t.gamma, 0.5)

    def test_builds_fehr_schmidt(self) -> None:
        t = build_utility_transform({"type": "FehrSchmidt", "alpha": 0.4, "beta": 0.6})
        self.assertIsInstance(t, FehrSchmidtTransform)


if __name__ == "__main__":
    unittest.main()
