"""Compute Nash equilibria from a FAIRGAME ``payoffMatrix`` block.

Used to expand ``equilibria: "auto"`` in a config into the explicit list
of combination keys the analysis layer expects. Currently supports the
2-player canonical 4-combination matrix; for larger games the helper
returns an empty list and the caller falls back to whatever was declared
manually.

Depends on the optional ``nashpy`` package. If it isn't installed the
helper raises ``ImportError`` with a clear message.
"""

from __future__ import annotations

from typing import Any


def _two_player_payoff_arrays(
    matrix_block: dict[str, Any], language: str = "en"
) -> tuple[Any, Any] | None:
    """Build the (A, B) payoff arrays for nashpy from a FAIRGAME matrix block.

    Returns ``None`` when the matrix isn't the canonical 2x2 four-combination
    shape — the caller should treat that as "can't auto-resolve".
    """
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        return None

    strategies = (matrix_block.get("strategies") or {}).get(language) or {}
    weights = matrix_block.get("weights") or {}
    combinations = matrix_block.get("combinations") or {}
    weight_matrix = matrix_block.get("matrix") or {}

    # All four sub-blocks must be present and non-empty; otherwise the
    # game isn't fully specified and we can't compute equilibria honestly.
    if not (strategies and weights and combinations and weight_matrix):
        return None

    strategy_keys = list(strategies.keys())
    if len(strategy_keys) != 2:
        return None
    canonical = {
        ("strategy1", "strategy1"): "combination1",
        ("strategy1", "strategy2"): "combination2",
        ("strategy2", "strategy1"): "combination3",
        ("strategy2", "strategy2"): "combination4",
    }
    if not all(k in combinations and k in weight_matrix for k in canonical.values()):
        return None
    # Verify combination shape matches the canonical 2x2 ordering.
    for combo_keys, combo_name in canonical.items():
        if tuple(combinations[combo_name]) != combo_keys:
            return None

    def cell(combo_name: str) -> tuple[float, float]:
        wkeys = weight_matrix[combo_name]
        return float(weights.get(wkeys[0], 0.0)), float(weights.get(wkeys[1], 0.0))

    # nashpy convention: A is row player's payoffs, B is column player's.
    a = np.array(
        [
            [cell("combination1")[0], cell("combination2")[0]],
            [cell("combination3")[0], cell("combination4")[0]],
        ]
    )
    b = np.array(
        [
            [cell("combination1")[1], cell("combination2")[1]],
            [cell("combination3")[1], cell("combination4")[1]],
        ]
    )
    return a, b


def compute_nash_equilibria(
    matrix_block: dict[str, Any], language: str = "en", direction: str = "reward"
) -> list[str]:
    """Return the list of combination keys that are pure-strategy Nash equilibria.

    ``direction`` is the config's ``payoffDirection``: ``"reward"`` treats the
    weights as utilities to maximise (default), ``"penalty"`` as costs to
    minimise (the equilibria of the negated game).

    Mixed-strategy equilibria are intentionally excluded — they don't
    correspond to a single combination key in the FAIRGAME schema.
    """
    try:
        import nashpy as nash
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised when nashpy missing
        raise ImportError(
            "nashpy is required for equilibria='auto'. Install with `pip install nashpy`."
        ) from exc

    arrays = _two_player_payoff_arrays(matrix_block, language)
    if arrays is None:
        return []

    a, b = arrays
    if direction == "penalty":
        a, b = -a, -b
    game = nash.Game(a, b)
    equilibria: list[str] = []
    combo_for_pure = {
        (0, 0): "combination1",
        (0, 1): "combination2",
        (1, 0): "combination3",
        (1, 1): "combination4",
    }
    seen = set()
    for sigma_row, sigma_col in game.support_enumeration():
        # Pure strategies are 0/1-valued indicator vectors.
        if not (np.allclose(sigma_row.sum(), 1) and np.allclose(sigma_col.sum(), 1)):
            continue
        if sigma_row.max() < 0.99 or sigma_col.max() < 0.99:
            continue
        i = int(np.argmax(sigma_row))
        j = int(np.argmax(sigma_col))
        combo = combo_for_pure.get((i, j))
        if combo and combo not in seen:
            seen.add(combo)
            equilibria.append(combo)
    return equilibria
