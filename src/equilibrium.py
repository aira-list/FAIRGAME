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

from typing import Any, Dict, List, Tuple


def _two_player_payoff_arrays(
    matrix_block: Dict[str, Any], language: str = "en"
) -> Tuple[Any, Any] | None:
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

    def cell(combo_name: str) -> Tuple[float, float]:
        wkeys = weight_matrix[combo_name]
        return float(weights.get(wkeys[0], 0.0)), float(weights.get(wkeys[1], 0.0))

    # nashpy convention: A is row player's payoffs, B is column player's.
    a = np.array([[cell("combination1")[0], cell("combination2")[0]],
                  [cell("combination3")[0], cell("combination4")[0]]])
    b = np.array([[cell("combination1")[1], cell("combination2")[1]],
                  [cell("combination3")[1], cell("combination4")[1]]])
    return a, b


def compute_nash_equilibria(matrix_block: Dict[str, Any], language: str = "en") -> List[str]:
    """Return the list of combination keys that are pure-strategy Nash equilibria.

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
    game = nash.Game(a, b)
    equilibria: List[str] = []
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


def expand_auto_equilibria(config: Dict[str, Any]) -> Dict[str, Any]:
    """Replace ``equilibria: "auto"`` in ``config`` with the resolved list.

    Returns the (possibly mutated) config — intended to be called *after*
    payoff-matrix transformation but *before* the rest of the validator.
    Leaves the config alone if ``equilibria`` is anything other than the
    string ``"auto"``.
    """
    if config.get("equilibria") != "auto":
        return config
    matrix_block = config.get("payoffMatrix") or {}
    languages = config.get("languages") or ["en"]
    language = languages[0]
    config["equilibria"] = compute_nash_equilibria(matrix_block, language)
    return config
