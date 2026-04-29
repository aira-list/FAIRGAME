"""Tests for :mod:`src.utility`."""

from __future__ import annotations

import math
import unittest

from src.utility import (
    CRRATransform,
    FehrSchmidtTransform,
    IdentityTransform,
    UtilityTransform,
    build_utility_transform,
)


# ---------------------------------------------------------------------------
# IdentityTransform
# ---------------------------------------------------------------------------

class TestIdentity(unittest.TestCase):
    def test_passes_payoffs_through_unchanged(self) -> None:
        self.assertEqual(IdentityTransform().transform([1, 2, 3]), [1, 2, 3])

    def test_returns_a_new_list_not_same_object(self) -> None:
        # Don't expose the input list to mutation by callers.
        original = [1, 2, 3]
        result = IdentityTransform().transform(original)
        self.assertIsNot(result, original)

    def test_handles_empty_input(self) -> None:
        self.assertEqual(IdentityTransform().transform([]), [])

    def test_preserves_floats(self) -> None:
        self.assertEqual(IdentityTransform().transform([1.5, 2.5]), [1.5, 2.5])

    def test_handles_negative_values(self) -> None:
        self.assertEqual(IdentityTransform().transform([-3, 0, 3]), [-3, 0, 3])

    def test_name_is_identity(self) -> None:
        self.assertEqual(IdentityTransform().name, "identity")


# ---------------------------------------------------------------------------
# CRRATransform
# ---------------------------------------------------------------------------

class TestCRRA(unittest.TestCase):
    def test_log_case_when_gamma_one(self) -> None:
        # offset=1 default → ln(x + 1). For x = e - 1 → ln(e) = 1.
        result = CRRATransform(gamma=1.0).transform([math.e - 1])
        self.assertAlmostEqual(result[0], 1.0, places=5)

    def test_risk_neutral_gamma_zero_preserves_ordering(self) -> None:
        u = CRRATransform(gamma=0.0, offset=1.0).transform([1.0, 2.0, 3.0])
        self.assertEqual(u, sorted(u))

    def test_higher_gamma_compresses_payoff_spread(self) -> None:
        # Risk aversion shrinks the gap between high and low outcomes.
        risk_neutral = CRRATransform(gamma=0.0).transform([1.0, 5.0])
        risk_averse = CRRATransform(gamma=0.8).transform([1.0, 5.0])
        spread_neutral = risk_neutral[1] - risk_neutral[0]
        spread_averse = risk_averse[1] - risk_averse[0]
        self.assertGreater(spread_neutral, spread_averse)

    def test_strictly_increasing_in_payoff(self) -> None:
        # For any γ ≥ 0 with offset > 0, u(x) is strictly increasing in x.
        for gamma in [0.0, 0.5, 1.0, 2.0]:
            u = CRRATransform(gamma=gamma).transform([1.0, 2.0, 3.0, 10.0])
            self.assertEqual(u, sorted(u), msg=f"non-monotone at γ={gamma}")

    def test_output_length_matches_input(self) -> None:
        for gamma in [0.0, 1.0, 2.0]:
            self.assertEqual(len(CRRATransform(gamma=gamma).transform([1, 2, 3])), 3)

    def test_negative_gamma_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            CRRATransform(gamma=-0.1)
        self.assertIn("gamma", str(ctx.exception).lower())

    def test_zero_or_negative_shifted_payoff_raises(self) -> None:
        # offset=0 + payoff=0 → log(0) = -inf, power blows up.
        with self.assertRaises(ValueError) as ctx:
            CRRATransform(gamma=0.5, offset=0.0).transform([0.0])
        self.assertIn("positive", str(ctx.exception).lower())

    def test_negative_payoff_with_small_offset_rejected(self) -> None:
        # Payoff -2 + offset 1 = -1 (still negative). Should raise.
        with self.assertRaises(ValueError):
            CRRATransform(gamma=0.5, offset=1.0).transform([-2.0])

    def test_gamma_one_returns_log_for_each_input(self) -> None:
        # Multiple values, all under the log branch.
        result = CRRATransform(gamma=1.0).transform([0.0, 1.0, math.e - 1])
        self.assertAlmostEqual(result[0], math.log(1.0), places=5)
        self.assertAlmostEqual(result[1], math.log(2.0), places=5)
        self.assertAlmostEqual(result[2], 1.0, places=5)

    def test_name_is_crra(self) -> None:
        self.assertEqual(CRRATransform(gamma=0.5).name, "crra")


# ---------------------------------------------------------------------------
# FehrSchmidtTransform
# ---------------------------------------------------------------------------

class TestFehrSchmidt(unittest.TestCase):
    def test_equal_payoffs_unchanged(self) -> None:
        u = FehrSchmidtTransform(alpha=0.5, beta=0.5).transform([1.0, 1.0, 1.0])
        self.assertEqual(u, [1.0, 1.0, 1.0])

    def test_envy_reduces_underdog_utility(self) -> None:
        # Agent 0 earns 0, agent 1 earns 4. Agent 0 envies → u_0 < 0.
        u = FehrSchmidtTransform(alpha=0.5, beta=0.0).transform([0.0, 4.0])
        self.assertLess(u[0], 0.0)

    def test_guilt_reduces_winner_utility(self) -> None:
        u = FehrSchmidtTransform(alpha=0.0, beta=0.5).transform([4.0, 0.0])
        self.assertLess(u[0], 4.0)

    def test_zero_alpha_zero_beta_is_identity(self) -> None:
        u = FehrSchmidtTransform(alpha=0.0, beta=0.0).transform([1.0, 5.0, 10.0])
        self.assertEqual(u, [1.0, 5.0, 10.0])

    def test_higher_alpha_reduces_envy_more(self) -> None:
        weak = FehrSchmidtTransform(alpha=0.1, beta=0.0).transform([0.0, 4.0])
        strong = FehrSchmidtTransform(alpha=0.9, beta=0.0).transform([0.0, 4.0])
        # Larger α => deeper underdog penalty.
        self.assertLess(strong[0], weak[0])

    def test_three_agent_distribution(self) -> None:
        u = FehrSchmidtTransform(alpha=0.4, beta=0.6).transform([1.0, 5.0, 9.0])
        # Output length matches input.
        self.assertEqual(len(u), 3)
        # The middle agent has both an inferior and a superior — its
        # utility is bracketed between its raw payoff and somewhere lower.
        self.assertLess(u[1], 5.0)

    def test_empty_input_yields_empty_output(self) -> None:
        self.assertEqual(FehrSchmidtTransform(alpha=0.5, beta=0.5).transform([]), [])

    def test_singleton_returns_payoff_unchanged(self) -> None:
        # No comparisons possible with one agent → no inequity penalty.
        u = FehrSchmidtTransform(alpha=0.5, beta=0.5).transform([7.0])
        self.assertEqual(u, [7.0])

    def test_negative_alpha_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            FehrSchmidtTransform(alpha=-0.1, beta=0.0)
        self.assertIn("non-negative", str(ctx.exception).lower())

    def test_negative_beta_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FehrSchmidtTransform(alpha=0.0, beta=-0.1)

    def test_name_is_fehr_schmidt(self) -> None:
        self.assertEqual(FehrSchmidtTransform(alpha=0.4, beta=0.6).name, "fehr_schmidt")


# ---------------------------------------------------------------------------
# build_utility_transform factory
# ---------------------------------------------------------------------------

class TestBuildFromConfig(unittest.TestCase):
    def test_none_config_returns_identity(self) -> None:
        self.assertIsInstance(build_utility_transform(None), IdentityTransform)

    def test_empty_dict_returns_identity(self) -> None:
        self.assertIsInstance(build_utility_transform({}), IdentityTransform)

    def test_unknown_type_rejected_with_known_list(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_utility_transform({"type": "Bogus"})
        self.assertIn("Bogus", str(ctx.exception))

    def test_builds_crra_with_gamma(self) -> None:
        t = build_utility_transform({"type": "CRRA", "gamma": 0.5})
        self.assertIsInstance(t, CRRATransform)
        self.assertAlmostEqual(t.gamma, 0.5)

    def test_builds_crra_via_lowercase_alias(self) -> None:
        t = build_utility_transform({"type": "crra", "gamma": 0.3})
        self.assertIsInstance(t, CRRATransform)

    def test_builds_fehr_schmidt(self) -> None:
        t = build_utility_transform({"type": "FehrSchmidt", "alpha": 0.4, "beta": 0.6})
        self.assertIsInstance(t, FehrSchmidtTransform)
        self.assertAlmostEqual(t.alpha, 0.4)
        self.assertAlmostEqual(t.beta, 0.6)

    def test_builds_fehr_schmidt_via_dash_alias(self) -> None:
        t = build_utility_transform({"type": "fehr-schmidt", "alpha": 0.4, "beta": 0.6})
        self.assertIsInstance(t, FehrSchmidtTransform)

    def test_returns_subclass_of_utility_transform(self) -> None:
        for cfg in (None, {"type": "CRRA", "gamma": 0.5}, {"type": "FehrSchmidt", "alpha": 0.0, "beta": 0.0}):
            self.assertIsInstance(build_utility_transform(cfg), UtilityTransform)

    def test_factory_passes_through_offset(self) -> None:
        t = build_utility_transform({"type": "CRRA", "gamma": 0.5, "offset": 5.0})
        self.assertAlmostEqual(t.offset, 5.0)


class TestFehrSchmidtNormalisation(unittest.TestCase):
    """The (n-1) divisor matters: dropping it would bias the per-other
    average term, and using just n (not n-1) would systematically
    under-penalise inequity in three+ player games."""

    def test_three_agent_envy_uses_n_minus_one_divisor(self) -> None:
        # With α=1.0, β=0, payoffs [0, 4, 8]:
        #   agent 0 envy = (4 + 8) / (n-1) = 12 / 2 = 6.0 → utility = 0 - 6 = -6.0
        # Mutation that uses /n=3 instead would yield -4.0; /1 (no divisor)
        # would yield -12.0. Pinning -6.0 catches both.
        u = FehrSchmidtTransform(alpha=1.0, beta=0.0).transform([0.0, 4.0, 8.0])
        self.assertAlmostEqual(u[0], -6.0, places=9)

    def test_three_agent_guilt_uses_n_minus_one_divisor(self) -> None:
        # α=0, β=1, payoffs [0, 4, 8]:
        #   agent 2 guilt = ((8-0) + (8-4)) / 2 = 6.0 → utility = 8 - 6 = 2.0
        u = FehrSchmidtTransform(alpha=0.0, beta=1.0).transform([0.0, 4.0, 8.0])
        self.assertAlmostEqual(u[2], 2.0, places=9)


if __name__ == "__main__":
    unittest.main()
