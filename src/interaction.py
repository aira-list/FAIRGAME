"""Agent interaction graph: who can see whom, and who can message whom.

By default FAIRGAME runs a *complete* interaction graph — every agent
observes and can broadcast to every other agent. This module lets a
configuration replace that implicit clique with an explicit, directed
topology, mirroring how :mod:`src.trust` and ``FakeCommunicationConfig``
attach optional per-game behaviour to a :class:`~src.fairgame.FairGame`.

Model
-----
A single directed graph. Each ordered pair ``(from, to)`` carries one of
three ordinal levels::

    none  <  see  <  talk

* ``see`` (thin edge)  — the target may observe the source's plays
  (strategy / score / belief), but receives no messages.
* ``talk`` (wide edge) — everything ``see`` grants, plus the source's
  broadcast message is delivered to the target. ``talk`` therefore
  subsumes ``see``: you cannot broadcast over a thin edge.

Direction convention: an edge ``A -> B`` means information flows *from A
to B* — i.e. ``B`` perceives ``A``. So with ``A -> B = talk`` and
``B -> A = see``, ``B`` sees and hears ``A`` while ``A`` only sees ``B``.

The graph is purely informational: it governs what each agent's prompt
shows, never who plays whom or how payoffs are scored. It composes on top
of the trust mechanism (an agent that did not pay to ``LOOK`` sees nothing
regardless of the graph).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

NONE = "none"
SEE = "see"
TALK = "talk"

# Ordinal rank so ``talk`` subsumes ``see`` subsumes ``none``.
_RANK = {NONE: 0, SEE: 1, TALK: 2}

# Friendly aliases accepted in configs / the GUI.
_ALIASES = {
    "none": NONE,
    "off": NONE,
    "no": NONE,
    "0": NONE,
    "see": SEE,
    "visibility": SEE,
    "visible": SEE,
    "observe": SEE,
    "watch": SEE,
    "1": SEE,
    "talk": TALK,
    "message": TALK,
    "broadcast": TALK,
    "communicate": TALK,
    "comm": TALK,
    "2": TALK,
}


def coerce_level(value: Any) -> str:
    """Map a config/GUI level value to a canonical ``none``/``see``/``talk``."""
    key = str(value).strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    raise ValueError(f"interaction level must be one of none/see/talk; got {value!r}.")


class InteractionGraph:
    """A directed visibility + communication graph over agent names."""

    def __init__(
        self,
        agent_names: Sequence[str],
        *,
        default_level: str = TALK,
        edges: dict[tuple[str, str], str] | None = None,
        directed: bool = True,
    ) -> None:
        self._names: list[str] = list(agent_names)
        self._name_set = set(self._names)
        self._default = coerce_level(default_level)
        self._directed = bool(directed)
        # Resolved overrides keyed by (from, to). Self edges are meaningless
        # (an agent always perceives itself) and are dropped.
        self._edges: dict[tuple[str, str], str] = {}
        for (frm, to), lvl in (edges or {}).items():
            if frm == to:
                continue
            self._require_known(frm)
            self._require_known(to)
            self._edges[(frm, to)] = coerce_level(lvl)

    # ---- Construction ----------------------------------------------------

    @classmethod
    def complete(cls, agent_names: Sequence[str]) -> InteractionGraph:
        """The default clique: everyone sees and can message everyone."""
        return cls(agent_names, default_level=TALK)

    @classmethod
    def from_config(cls, config: dict[str, Any], agent_names: Sequence[str]) -> InteractionGraph:
        """Build from a raw config dict's optional ``"interaction"`` block.

        Absent / falsy block → a complete graph (today's behaviour), so any
        configuration that predates this feature is unaffected.
        """
        block = config.get("interaction")
        if not block:
            return cls.complete(agent_names)

        default = coerce_level(block.get("default", TALK))
        directed = bool(block.get("directed", True))
        edges: dict[tuple[str, str], str] = {}
        raw_edges = block.get("edges", []) or []
        if not isinstance(raw_edges, list):
            raise ValueError("interaction.edges must be a list.")
        for entry in raw_edges:
            if not isinstance(entry, dict) or "from" not in entry or "to" not in entry:
                raise ValueError("each interaction edge must have 'from' and 'to'.")
            frm = entry["from"]
            to = entry["to"]
            lvl = coerce_level(entry.get("level", default))
            edges[(frm, to)] = lvl
            if not directed:
                edges[(to, frm)] = lvl
        return cls(agent_names, default_level=default, edges=edges, directed=directed)

    def _require_known(self, name: str) -> None:
        if name not in self._name_set:
            raise ValueError(
                f"interaction edge references unknown agent {name!r}; known agents: {self._names}."
            )

    # ---- Queries ---------------------------------------------------------

    def level(self, frm: str, to: str) -> str:
        """The information-flow level along ``frm -> to``.

        An agent always perceives itself, so a self pair is ``talk``.
        """
        if frm == to:
            return TALK
        return self._edges.get((frm, to), self._default)

    def sees(self, viewer: str, source: str) -> bool:
        """Whether ``viewer`` may observe ``source``'s plays."""
        return _RANK[self.level(source, viewer)] >= _RANK[SEE]

    def hears(self, viewer: str, source: str) -> bool:
        """Whether ``viewer`` receives ``source``'s broadcast messages."""
        return _RANK[self.level(source, viewer)] >= _RANK[TALK]

    @property
    def is_fully_connected(self) -> bool:
        """True when the graph is equivalent to the default clique.

        Lets the round runner skip filtering entirely (and guarantees exact
        backward-compatible behaviour) for the common case.
        """
        if self._default != TALK:
            return False
        return all(lvl == TALK for lvl in self._edges.values())

    # ---- Serialisation ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """A serialisable view for run metadata / the game description."""
        return {
            "directed": self._directed,
            "default": self._default,
            "edges": [
                {"from": frm, "to": to, "level": lvl}
                for (frm, to), lvl in sorted(self._edges.items())
            ],
        }
