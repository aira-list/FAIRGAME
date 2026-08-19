"""Game-theoretic integrity of the shipped starter library.

Every configuration in ``starter_library/configurations/`` ships a payoff
matrix that claims to be a specific game class (PD, Stag Hunt, Snowdrift,
Harmony, Battle of the Sexes, ...). These are static invariants over the
shipped JSON: the weights must actually satisfy the class-defining payoff
inequalities, any explicitly declared ``equilibria`` must be the true
pure-strategy Nash equilibria of the shipped matrix, and every declared
``paretoOptimalSum`` must equal the maximum cell sum (the convention every
consumer of ``welfare_efficiency`` assumes).

A drift here silently corrupts equilibrium-rate and efficiency metrics for
anyone running the seeds, so these tests fail loudly instead.
"""

from __future__ import annotations

import unittest

from src.game_theory.equilibrium import compute_nash_equilibria
from web_api.seeds import SEED_CONFIGURATIONS

CONFIGS_BY_ID = {cfg["id"]: cfg for cfg in SEED_CONFIGURATIONS}


def _runnable_matrices(cfg: dict) -> list[tuple[str, dict]]:
    """Every (label, payoffMatrix) a configuration can run with."""
    gc = cfg.get("game_config", {})
    out = []
    if gc.get("payoffMatrix"):
        out.append((cfg["id"], gc["payoffMatrix"]))
    for variation in cfg.get("variations") or []:
        if variation.get("axis") == "payoffMatrix":
            out.append((f"{cfg['id']}:{variation.get('name')}", variation["value"]))
    return out


def _is_canonical_two_player(matrix: dict) -> bool:
    combos = matrix.get("combinations") or {}
    return set(combos) == {f"combination{i}" for i in (1, 2, 3, 4)} and all(
        isinstance(s, str) for pair in combos.values() for s in pair
    )


def _cell(matrix: dict, combo: str) -> tuple[float, float]:
    weights = matrix["weights"]
    wkeys = matrix["matrix"][combo]
    return float(weights[wkeys[0]]), float(weights[wkeys[1]])


def _rtsp(matrix: dict) -> tuple[float, float, float, float]:
    """(R, T, S, P) under the canonical combination layout.

    combination1 = both cooperate, combination2 = (cooperate, defect) so the
    first weight is the lone cooperator's Sucker payoff and the second the
    defector's Temptation, combination4 = both defect.
    """
    r = _cell(matrix, "combination1")[0]
    s, t = _cell(matrix, "combination2")
    p = _cell(matrix, "combination4")[0]
    return r, t, s, p


class TestDeclaredEquilibriaAreTruePureNash(unittest.TestCase):
    def test_explicit_equilibria_match_computed(self) -> None:
        checked = 0
        for cfg in SEED_CONFIGURATIONS:
            declared = cfg.get("game_config", {}).get("equilibria")
            if not isinstance(declared, list) or not declared:
                continue
            for label, matrix in _runnable_matrices(cfg):
                if not _is_canonical_two_player(matrix):
                    continue
                computed = compute_nash_equilibria(matrix, "en")
                self.assertCountEqual(
                    declared,
                    computed,
                    f"{label}: declared equilibria {declared} but the shipped "
                    f"matrix's pure Nash equilibria are {computed}",
                )
                checked += 1
        self.assertGreater(checked, 0, "no config with explicit equilibria was checked")


class TestGameClassOrderings(unittest.TestCase):
    def test_every_pd_matrix_is_a_pd(self) -> None:
        pd_configs = [c for c in SEED_CONFIGURATIONS if c["game_type_id"] == "gt_pd"]
        self.assertGreater(len(pd_configs), 0)
        for cfg in pd_configs:
            for label, matrix in _runnable_matrices(cfg):
                if not _is_canonical_two_player(matrix):
                    continue
                r, t, s, p = _rtsp(matrix)
                self.assertTrue(
                    t > r > p > s,
                    f"{label}: PD needs T>R>P>S, got T={t} R={r} P={p} S={s}",
                )
                self.assertGreater(2 * r, t + s, f"{label}: PD convention needs 2R > T+S")

    def test_snowdrift_is_chicken_not_pd(self) -> None:
        matrices = _runnable_matrices(CONFIGS_BY_ID["seed_cfg_snowdrift"])
        self.assertTrue(matrices)
        for label, matrix in matrices:
            r, t, s, p = _rtsp(matrix)
            self.assertTrue(
                t > r > s > p,
                f"{label}: Snowdrift/Chicken needs T>R>S>P (lone cooperator "
                f"beats mutual defection), got T={t} R={r} S={s} P={p}",
            )

    def test_stag_hunt_ordering(self) -> None:
        for label, matrix in _runnable_matrices(CONFIGS_BY_ID["seed_cfg_stag"]):
            r, t, s, p = _rtsp(matrix)
            self.assertTrue(
                r > t >= p > s,
                f"{label}: Stag Hunt needs R>T>=P>S, got R={r} T={t} P={p} S={s}",
            )

    def test_battle_diagonal_is_asymmetric_and_mirrored(self) -> None:
        """BoS coordination cells must pay the two players differently, with
        the preference reversed between the two conventions — matching what
        the shipped template announces to the agents."""
        for label, matrix in _runnable_matrices(CONFIGS_BY_ID["seed_cfg_battle"]):
            c1 = _cell(matrix, "combination1")
            c4 = _cell(matrix, "combination4")
            self.assertNotEqual(
                c1[0],
                c1[1],
                f"{label}: symmetric coordination cell {c1} is not Battle of "
                "the Sexes — each convention must favour one player",
            )
            self.assertEqual(
                c1,
                tuple(reversed(c4)),
                f"{label}: combination4 {c4} must mirror combination1 {c1}",
            )
            # Both coordination outcomes must beat miscoordination for both.
            for m in ("combination2", "combination3"):
                mc = _cell(matrix, m)
                self.assertTrue(min(c1) > max(mc) and min(c4) > max(mc))


class TestParetoOptimalSumConvention(unittest.TestCase):
    def test_declared_pareto_sum_is_max_cell_sum(self) -> None:
        checked = 0
        for cfg in SEED_CONFIGURATIONS:
            declared = cfg.get("game_config", {}).get("paretoOptimalSum")
            if declared is None:
                continue
            for label, matrix in _runnable_matrices(cfg):
                if not _is_canonical_two_player(matrix):
                    continue
                max_cell_sum = max(sum(_cell(matrix, combo)) for combo in matrix["combinations"])
                self.assertEqual(
                    float(declared),
                    max_cell_sum,
                    f"{label}: paretoOptimalSum={declared} but the matrix's "
                    f"maximum cell sum is {max_cell_sum}; welfare_efficiency "
                    "divides by this value",
                )
                checked += 1
        self.assertGreater(checked, 0)


class TestBehaviouralParameters(unittest.TestCase):
    def test_fehr_schmidt_envy_at_least_guilt(self) -> None:
        checked = 0
        for cfg in SEED_CONFIGURATIONS:
            ut = cfg.get("game_config", {}).get("utilityTransform") or {}
            if str(ut.get("type", "")).lower().replace("-", "_") not in (
                "fehrschmidt",
                "fehr_schmidt",
            ):
                continue
            alpha, beta = float(ut["alpha"]), float(ut["beta"])
            self.assertGreaterEqual(
                alpha,
                beta,
                f"{cfg['id']}: Fehr-Schmidt convention requires envy alpha >= "
                f"guilt beta (got alpha={alpha}, beta={beta})",
            )
            self.assertLessEqual(beta, 1.0)
            checked += 1
        self.assertGreater(checked, 0)

    def test_opponent_probs_use_percent_scale(self) -> None:
        """The engine renders opponentPersonalityProb verbatim into
        '...has a probability of {value}% ...', so seed values must be
        percentages; a value strictly between 0 and 1 is a 0-1-scale mixup."""
        for cfg in SEED_CONFIGURATIONS:
            probs = (cfg.get("game_config", {}).get("agents") or {}).get(
                "opponentPersonalityProb"
            ) or []
            for p in probs:
                self.assertFalse(
                    0 < float(p) < 1,
                    f"{cfg['id']}: opponentPersonalityProb {p} looks like a "
                    "0-1 fraction; the prompt renders it verbatim as a percent",
                )


if __name__ == "__main__":
    unittest.main()
