"""Trust / costly-monitoring configuration.

FAIRGAME-Trust adds a voluntary, costly *monitoring* decision before the
strategy choice each round. An agent first decides whether to ``LOOK`` (pay a
monitoring cost to observe the opponent's history) or ``NO_LOOK`` (act on
trust with no information). This module holds the per-game configuration for
that mechanism; the round runner (:mod:`src.game.game_round`) and phase list
(:mod:`src.game.phases`) consume it, mirroring how ``FakeCommunicationConfig``
drives the communication phase.

v1 supports a single ``historyScope`` value, ``"full"``: when an agent pays to
``LOOK`` it sees the full prior history; otherwise it sees nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LOOK = "LOOK"
NO_LOOK = "NO_LOOK"


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
    # Only "full" is supported in v1: a paying agent sees the whole history.
    history_scope: str = "full"

    _SUPPORTED_SCOPES = ("full",)

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

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> TrustConfig:
        """Build from a raw config dict's optional ``"trust"`` block."""
        block = config.get("trust") or {}
        if not _str2bool(block.get("enabled", False)):
            return cls(enabled=False)
        return cls(
            enabled=True,
            look_cost=float(block.get("lookCost", 0.0) or 0.0),
            history_scope=str(block.get("historyScope", "full")),
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
