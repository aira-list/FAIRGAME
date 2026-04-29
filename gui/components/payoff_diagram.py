"""Render a tiny 2×2 payoff matrix as inline HTML for scenario cards."""

from __future__ import annotations

from typing import Any, Dict


def render_2x2_payoff_html(config: Dict[str, Any]) -> str:
    """Return an HTML table showing the 2x2 payoff structure of ``config``.

    Looks for the canonical four-combination matrix; returns an empty
    string when the structure isn't 2x2 (we don't try to render N×N).
    """
    pm = config.get("payoffMatrix") or {}
    weights = pm.get("weights") or {}
    matrix = pm.get("matrix") or {}
    strategies = (pm.get("strategies") or {}).get("en") or {}

    if not weights or not matrix or not strategies:
        return ""
    combo_keys = ["combination1", "combination2", "combination3", "combination4"]
    if not all(k in matrix for k in combo_keys):
        return ""

    # Resolve weight keys → numeric payoffs for each cell.
    cells = []
    for combo_key in combo_keys:
        w_keys = matrix[combo_key]
        if len(w_keys) != 2:
            return ""
        cells.append((weights.get(w_keys[0], "?"), weights.get(w_keys[1], "?")))

    s1 = strategies.get("strategy1", "A")
    s2 = strategies.get("strategy2", "B")

    def cell(values):
        a, b = values
        return f"<span style='color:#1d4ed8'>{a}</span> / <span style='color:#be123c'>{b}</span>"

    return f"""
    <table style='border-collapse:collapse;font-size:0.8rem;margin-top:0.5rem'>
      <tr>
        <th style='padding:2px 6px;font-weight:500;color:#64748b'></th>
        <th style='padding:2px 6px;font-weight:500;color:#64748b'>{s1}</th>
        <th style='padding:2px 6px;font-weight:500;color:#64748b'>{s2}</th>
      </tr>
      <tr>
        <th style='padding:2px 6px;font-weight:500;color:#64748b;text-align:right'>{s1}</th>
        <td style='padding:2px 8px;border:1px solid #e2e8f0'>{cell(cells[0])}</td>
        <td style='padding:2px 8px;border:1px solid #e2e8f0'>{cell(cells[1])}</td>
      </tr>
      <tr>
        <th style='padding:2px 6px;font-weight:500;color:#64748b;text-align:right'>{s2}</th>
        <td style='padding:2px 8px;border:1px solid #e2e8f0'>{cell(cells[2])}</td>
        <td style='padding:2px 8px;border:1px solid #e2e8f0'>{cell(cells[3])}</td>
      </tr>
    </table>
    """
