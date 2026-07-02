"""Generate per-pair configs for round-robin tournaments.

A tournament with N agents collapses into N·(N−1)/2 (or N·(N−1) when
``symmetric=False``) two-player sub-games. Each sub-game inherits the
top-level config but slices the agents block, opponent-prior list, and
``llms`` mapping to just the chosen pair.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.utils.rng import combine_seed


class TournamentBuilder:
    """Pure-config slicing for round-robin tournaments. Holds no state."""

    def pairs(
        self,
        names: Sequence[str],
        mode: str = "round_robin",
        symmetric: bool = True,
    ) -> list[tuple[str, str]]:
        """Return the ordered list of agent-name pairs to play."""
        if mode != "round_robin":
            raise ValueError(f"Unsupported tournament mode {mode!r}.")
        if len(names) < 2:
            raise ValueError("Tournament needs at least 2 agents.")

        result: list[tuple[str, str]] = []
        for i, ai in enumerate(names):
            for j, aj in enumerate(names):
                if ai == aj:
                    continue
                if symmetric and j <= i:
                    continue
                result.append((ai, aj))
        return result

    def build_pair_config(
        self,
        config: dict[str, Any],
        pair: tuple[str, str],
        pair_idx: int,
        resolved_seed: Any = None,
    ) -> tuple[dict[str, Any], Any]:
        """Materialise a config that has only the two agents in ``pair``.

        Returns ``(pair_config, pair_seed)``. Distinct ``pair_idx`` values
        derive a fresh resolved seed (when ``resolved_seed`` is set) so
        deterministic multi-seed runs don't collide between pairs. Plain
        addition (``seed + pair_idx``) collided across axes — e.g. (base 10,
        pair 1) == (base 11, pair 0); ``combine_seed`` folds the two axes into
        a unique seed instead. The seed travels as an explicit value, never
        as a smuggled key inside the config dict.
        """
        pair_config = dict(config)
        pair_seed = (
            combine_seed(int(resolved_seed), pair_idx) if resolved_seed is not None else None
        )

        agents_block = dict(config["agents"])
        names = list(config["agents"]["names"])
        idx = [names.index(p) for p in pair]

        agents_block["names"] = list(pair)
        agents_block["personalities"] = {
            lang: [plist[i] for i in idx]
            for lang, plist in config["agents"]["personalities"].items()
        }
        if config["agents"].get("opponentPersonalityProb"):
            opp = config["agents"]["opponentPersonalityProb"]
            agents_block["opponentPersonalityProb"] = (
                [opp[i] for i in idx] if len(opp) == len(names) else opp
            )
        pair_config["agents"] = agents_block

        if isinstance(config.get("llms"), dict):
            pair_config["llms"] = {p: config["llms"][p] for p in pair}
        elif isinstance(config.get("llms"), list):
            pair_config["llms"] = [config["llms"][i] for i in idx]

        return pair_config, pair_seed
