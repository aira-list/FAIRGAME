"""Generate per-pair configs for round-robin tournaments.

A tournament with N agents collapses into N·(N−1)/2 (or N·(N−1) when
``symmetric=False``) two-player sub-games. Each sub-game inherits the
top-level config but slices the agents block, opponent-prior list, and
``llms`` mapping to just the chosen pair.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


class TournamentBuilder:
    """Pure-config slicing for round-robin tournaments. Holds no state."""

    def pairs(
        self,
        names: Sequence[str],
        mode: str = "round_robin",
        symmetric: bool = True,
    ) -> List[Tuple[str, str]]:
        """Return the ordered list of agent-name pairs to play."""
        if mode != "round_robin":
            raise ValueError(f"Unsupported tournament mode {mode!r}.")
        if len(names) < 2:
            raise ValueError("Tournament needs at least 2 agents.")

        result: List[Tuple[str, str]] = []
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
        config: Dict[str, Any],
        pair: Tuple[str, str],
        pair_idx: int,
    ) -> Dict[str, Any]:
        """Materialise a config that has only the two agents in ``pair``.

        Distinct ``pair_idx`` values bump the resolved seed (when set) so
        deterministic multi-seed runs don't collide between pairs.
        """
        pair_config = dict(config)
        if pair_config.get("_resolved_seed") is not None:
            pair_config["_resolved_seed"] = int(pair_config["_resolved_seed"]) + pair_idx

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

        return pair_config
