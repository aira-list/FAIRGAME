"""Trust / costly-monitoring configuration.

FAIRGAME-Trust adds a voluntary, costly *monitoring* decision before the
strategy choice each round. An agent first decides whether to ``LOOK`` (pay a
monitoring cost to observe the opponent's history) or ``NO_LOOK`` (act on
trust with no information). This module holds the per-game configuration for
that mechanism; the round runner (:mod:`src.game.game_round`) and phase list
(:mod:`src.game.phases`) consume it, mirroring how ``FakeCommunicationConfig``
drives the communication phase.

``historyScope`` decides what a paid ``LOOK`` buys:

``full``
    the whole prior history (the original v2 behaviour, and the default).
``last_x``
    only the most recent ``historyRounds`` rounds.
``only_paid_to_look_last_1`` / ``paid_look_minus_1``
    the round immediately before the current one, *plus* every round the
    agent unlocked by paying in an earlier round. Under these scopes
    monitoring accumulates: a ``LOOK`` in round *t* keeps round *t-1* visible
    for the rest of the game.

``historyFields`` optionally narrows each revealed entry to a subset of its
fields (``["strategy", "score"]``, say), so paying to look need not disclose
messages or elicited beliefs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LOOK = "LOOK"
NO_LOOK = "NO_LOOK"

#: Scopes under which monitoring accumulates across rounds.
RETENTION_SCOPES = ("paid_look_minus_1", "only_paid_to_look_last_1")


def _str2bool(value: Any) -> bool:
    """Coerce JSON-ish truthy values ("True"/"true"/1/True) to ``bool``."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


@dataclass
class TrustConfig:
    """Per-game settings for the costly-monitoring (trust) mechanism."""

    enabled: bool = False
    look_cost: float = 0.0
    history_scope: str = "full"
    #: Rounds revealed under ``last_x``; ignored by the other scopes.
    history_rounds: int = 1
    #: Labels for the two decisions, surfaced to templates and result rows.
    actions: list[str] = field(default_factory=lambda: [LOOK, NO_LOOK])
    #: Entry fields a paid look reveals; ``None`` reveals the whole entry.
    history_fields: list[str] | None = None

    _SUPPORTED_SCOPES = ("full", "last_x", *RETENTION_SCOPES)

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        if self.look_cost < 0:
            raise ValueError(f"trust.lookCost must be >= 0; got {self.look_cost}.")
        if self.history_scope not in self._SUPPORTED_SCOPES:
            raise ValueError(
                f"trust.historyScope must be one of {self._SUPPORTED_SCOPES}; "
                f"got {self.history_scope!r}."
            )
        if self.history_scope == "last_x" and self.history_rounds < 1:
            raise ValueError(
                f"trust.historyRounds must be >= 1 under historyScope 'last_x'; "
                f"got {self.history_rounds}."
            )
        if len(self.actions) != 2:
            raise ValueError(f"trust.actions must name exactly two actions; got {self.actions!r}.")

    @property
    def retains_unlocked_history(self) -> bool:
        """Whether a paid look keeps that round visible in later rounds."""
        return self.history_scope in RETENTION_SCOPES

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> TrustConfig:
        """Build from a raw config dict's optional ``"trust"`` block."""
        block = config.get("trust") or {}
        if not _str2bool(block.get("enabled", False)):
            return cls(enabled=False)
        fields_raw = block.get("historyFields")
        return cls(
            enabled=True,
            look_cost=float(block.get("lookCost", 0.0) or 0.0),
            history_scope=str(block.get("historyScope", "full")),
            history_rounds=int(block.get("historyRounds", 1) or 1),
            actions=list(block.get("actions") or [LOOK, NO_LOOK]),
            history_fields=list(fields_raw) if fields_raw else None,
        )

    @staticmethod
    def parse_action(response_text: str) -> str:
        """Map a raw monitoring-decision response to ``LOOK`` / ``NO_LOOK``.

        Defaults to ``NO_LOOK`` on anything ambiguous — the conservative,
        no-cost choice — so a malformed model reply never silently incurs a
        monitoring cost. ``NO_LOOK`` is checked first because it contains the
        substring ``LOOK``.
        """
        if not response_text:
            return NO_LOOK
        cleaned = response_text.strip().upper().replace(" ", "_")
        if NO_LOOK in cleaned:
            return NO_LOOK
        if LOOK in cleaned:
            return LOOK
        return NO_LOOK
