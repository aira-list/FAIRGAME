"""The shipped templates must describe the game the engine actually scores.

Each starter configuration pairs a payoff matrix (what the engine attributes)
with a template (what the agent is told). These invariants bind the two:

* every payoff sentence's ``{weightN}`` wiring must match the configuration's
  ``matrix`` block — for BOTH seats, since the same template renders for
  every agent;
* the stated goal must match ``payoffDirection`` (all shipped seeds are
  reward-framed: "maximise", never "minimise"/"penalty");
* a configuration that enables a phase (``believe2``) must use a template
  that carries the corresponding block.

A drift here is the worst failure mode this project has: agents rationally
play the game they were TOLD while the metrics score the game in the MATRIX,
silently inverting cooperation/equilibrium results (this happened — the PD
family shipped penalty-framed prose over reward-scored weights).
"""

from __future__ import annotations

import re
import unittest

from web_api.seeds import SEED_CONFIGURATIONS, SEED_TEMPLATES

TEMPLATES_BY_KEY = {
    (t["game_type_id"], t["variation"], t["language"]): t["body"] for t in SEED_TEMPLATES
}

_PLACEHOLDER = re.compile(r"\{(strategy\d+|weight\d+|opponent\d+)\}")

# Sentence classifiers (EN + FR shipped templates).
_BOTH_MARKERS = ("both choose", "tous les deux")
_DIFFER_MARKERS = ("choose differently", "different options", "différemment")


def _placeholders(line: str) -> list[str]:
    return _PLACEHOLDER.findall(line)


def _matrices_for(cfg: dict) -> list[tuple[str, dict]]:
    out = []
    gc = cfg.get("game_config", {})
    if gc.get("payoffMatrix"):
        out.append((cfg["id"], gc["payoffMatrix"]))
    for variation in cfg.get("variations") or []:
        if variation.get("axis") == "payoffMatrix":
            out.append((f"{cfg['id']}:{variation.get('name')}", variation["value"]))
    return out


def _canonical_combos(pm: dict) -> dict[tuple[str, str], list[float]] | None:
    """(row_strategy, col_strategy) -> [row_payoff, col_payoff] as VALUES.

    Values, not weight-key names: the agent reads numbers, so two different
    keys holding the same number are the same statement (Battle's two zero
    cells legitimately use different keys in prose and matrix).
    """
    combos = pm.get("combinations") or {}
    matrix = pm.get("matrix") or {}
    weights = pm.get("weights") or {}
    out: dict[tuple[str, str], list[float]] = {}
    for name, strategies in combos.items():
        if not (isinstance(strategies, list) and len(strategies) == 2):
            return None  # not a 2-player canonical matrix
        if not all(isinstance(s, str) for s in strategies):
            return None
        try:
            out[tuple(strategies)] = [float(weights[k]) for k in matrix.get(name) or []]
        except (KeyError, TypeError, ValueError):
            return None
    return out


class TestSeedTemplatesMatchTheirMatrices(unittest.TestCase):
    def _template_for(self, cfg: dict, language: str) -> str | None:
        return TEMPLATES_BY_KEY.get((cfg.get("game_type_id"), cfg.get("variation"), language))

    def _values(self, pm: dict, weight_names: list[str]) -> list[float]:
        return [float(pm["weights"][w]) for w in weight_names]

    def _check_line(self, label, line, pm, combos, agent_names):
        """Assert one payoff sentence against the matrix (by VALUE).

        Returns the set of (row, col) strategy profiles the sentence pinned
        down; empty set = not a recognisable payoff statement.
        """
        ph = _placeholders(line)
        strategies = [p for p in ph if p.startswith("strategy")]
        weight_names = [p for p in ph if p.startswith("weight")]
        if not weight_names:
            return set()
        values = self._values(pm, weight_names)
        lower = line.lower()
        named = [n for n in agent_names if n in line]
        covered: set[tuple[str, str]] = set()

        # "If you choose {A} and {opponent1} chooses {B}, you get {wX} and
        # {opponent1} gets {wY}" — must hold from BOTH seats: matrix[(A,B)]
        # == [x, y] and matrix[(B,A)] == [y, x].
        if len(strategies) == 2 and len(values) == 2 and "opponent1" in ph:
            a, b = strategies
            x, y = values
            self.assertEqual(
                combos.get((a, b)),
                [x, y],
                f"{label}: prose says ({a} vs {b}) pays [{x}, {y}] but the "
                f"matrix says {combos.get((a, b))}",
            )
            self.assertEqual(
                combos.get((b, a)),
                [y, x],
                f"{label}: the same sentence read from the other seat needs "
                f"matrix[({b},{a})] == [{y}, {x}], got {combos.get((b, a))}",
            )
            return {(a, b), (b, a)}

        # "If you both choose {A}, Agent1 gets {wX} and Agent2 gets {wY}"
        # (asymmetric games anchor seats by agent name).
        if len(strategies) == 1 and len(values) == 2 and len(named) == 2:
            (a,) = strategies
            x, y = values
            ordered = sorted(named, key=line.index)
            expected = [x, y] if ordered == list(agent_names) else [y, x]
            self.assertEqual(
                combos.get((a, a)),
                expected,
                f"{label}: prose says both-{a} pays {expected} by seat but the "
                f"matrix says {combos.get((a, a))}",
            )
            return {(a, a)}

        # "If you both choose {A}, you both get {wX}".
        if len(strategies) == 1 and len(values) == 1 and any(m in lower for m in _BOTH_MARKERS):
            (a,) = strategies
            (x,) = values
            self.assertEqual(
                combos.get((a, a)),
                [x, x],
                f"{label}: prose says both-{a} pays [{x}, {x}] but the matrix "
                f"says {combos.get((a, a))}",
            )
            return {(a, a)}

        off_diagonal = [k for k in combos if k[0] != k[1]]
        diagonal = [k for k in combos if k[0] == k[1]]

        # "If you choose differently, ..." — applies to both off-diagonal cells.
        if not strategies and any(m in lower for m in _DIFFER_MARKERS):
            if len(values) == 1:
                (x,) = values
                for k in off_diagonal:
                    self.assertEqual(
                        combos[k],
                        [x, x],
                        f"{label}: prose says any miscoordination pays [{x}, {x}] "
                        f"but matrix[{k}] is {combos[k]}",
                    )
                covered.update(off_diagonal)
            elif len(values) == 2 and len(named) == 2:
                x, y = values
                ordered = sorted(named, key=line.index)
                expected = [x, y] if ordered == list(agent_names) else [y, x]
                for k in off_diagonal:
                    self.assertEqual(
                        combos[k],
                        expected,
                        f"{label}: prose says miscoordination pays {expected} by "
                        f"seat but matrix[{k}] is {combos[k]}",
                    )
                covered.update(off_diagonal)
            return covered

        # "If you both choose the same option, agent1 gets {wX} and agent2
        # gets {wY}" — applies to every diagonal cell, seats by name order.
        if not strategies and "same option" in lower and len(values) == 2 and len(named) == 2:
            x, y = values
            ordered = sorted(named, key=line.index)
            expected = [x, y] if ordered == list(agent_names) else [y, x]
            for k in diagonal:
                self.assertEqual(
                    combos[k],
                    expected,
                    f"{label}: prose says same-choice pays {expected} by seat "
                    f"but matrix[{k}] is {combos[k]}",
                )
            covered.update(diagonal)
            return covered

        return set()

    def test_two_player_payoff_sentences_match_matrix(self) -> None:
        checked_templates = 0
        for cfg in SEED_CONFIGURATIONS:
            gc = cfg.get("game_config", {})
            agent_names = list((gc.get("agents") or {}).get("names") or [])
            if len(agent_names) != 2 and cfg["id"] != "seed_cfg_pd_baseline_tournament":
                continue  # n-player volunteer handled separately
            for language in cfg.get("languages") or []:
                body = self._template_for(cfg, language)
                if body is None:
                    continue
                for label, pm in _matrices_for(cfg):
                    combos = _canonical_combos(pm)
                    if combos is None:
                        continue
                    covered: set[tuple[str, str]] = set()
                    for line in body.splitlines():
                        covered |= self._check_line(
                            f"{label}/{language}", line, pm, combos, agent_names[:2]
                        )
                    # Every cell of the matrix must be stated by some
                    # recognised payoff sentence: an unstated cell means the
                    # agent is not told part of the game it is scored on.
                    self.assertEqual(
                        covered,
                        set(combos),
                        f"{label}/{language}: template payoff sentences cover "
                        f"{sorted(covered)} but the matrix defines "
                        f"{sorted(combos)} (unstated or unrecognised cells; "
                        "extend the template or this test's patterns)",
                    )
                    checked_templates += 1
        self.assertGreater(checked_templates, 10, "fidelity test lost its inputs")

    def test_volunteer_template_matches_its_matrix_semantics(self) -> None:
        cfg = next(c for c in SEED_CONFIGURATIONS if c["id"] == "seed_cfg_volunteer")
        body = self._template_for(cfg, "en")
        self.assertIsNotNone(body)
        # The matrix rewards: lone/any volunteers (strategy2) w2, free-riders
        # w3 when someone volunteered, and w1 to everyone when nobody did.
        pm = cfg["game_config"]["payoffMatrix"]
        weights = pm["weights"]
        self.assertEqual((weights["weight1"], weights["weight2"], weights["weight3"]), (0, 5, 10))
        for combo in pm["combinations"].values():
            pairs = [tuple(p) for p in combo]
            volunteered = any(s == "strategy2" for s, _ in pairs)
            for strategy, weight in pairs:
                if not volunteered:
                    self.assertEqual(weight, "weight1")
                elif strategy == "strategy2":
                    self.assertEqual(weight, "weight2")
                else:
                    self.assertEqual(weight, "weight3")
        # And the prose must tell the same story: strategy2 is the volunteer
        # action, w2 the volunteer's payoff, w3 the free-rider's, w1 the
        # nobody-volunteered payoff.
        self.assertIn("'{strategy2}' (volunteer)", body)
        self.assertRegex(
            body, r"chose \{strategy2\} receives a payoff of \{weight2\}"
        )
        self.assertRegex(body, r"chose \{strategy1\} receives a payoff of \{weight3\}")
        self.assertRegex(
            body, r"no one chooses \{strategy2\}, all players receive a payoff of \{weight1\}"
        )

    def test_goal_framing_matches_payoff_direction(self) -> None:
        # Every shipped seed is reward-framed; its template must never ask
        # the agent to minimise or mention penalties.
        for (gt, variation, language), body in TEMPLATES_BY_KEY.items():
            lowered = body.lower()
            for banned in ("minimize", "minimise", "minimiser", "penalty", "pénalité"):
                self.assertNotIn(
                    banned,
                    lowered,
                    f"template ({gt}, {variation}, {language}) is penalty-framed "
                    "but every shipped configuration scores weights as rewards "
                    "(set payoffDirection: 'penalty' AND keep prose consistent "
                    "if a penalty seed is ever intended)",
                )

    def test_configs_enabling_believe2_have_the_block(self) -> None:
        for cfg in SEED_CONFIGURATIONS:
            gc = cfg.get("game_config", {})
            if not (gc.get("elicitBeliefs") and int(gc.get("tomOrder", 1)) >= 2):
                continue
            for language in cfg.get("languages") or []:
                body = self._template_for(cfg, language)
                self.assertIsNotNone(body, f"{cfg['id']}: no template for {language}")
                self.assertIn(
                    "{believe2}:",
                    body,
                    f"{cfg['id']}/{language}: elicitBeliefs + tomOrder>=2 but the "
                    "template has no {{believe2}}: block — the second-order phase "
                    "would silently never run",
                )


if __name__ == "__main__":
    unittest.main()
