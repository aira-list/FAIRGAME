"""Random decimal/hex tokens used as a noise channel between agents."""

from __future__ import annotations

import random
from typing import Any


class FakeCommunicationConfig:
    """Configuration holder for the optional fake-communication phase."""

    def __init__(
        self,
        enabled: bool = False,
        message_count: int = 1,
        base: str = "dec",
    ) -> None:
        self.enabled = enabled
        self.message_count = message_count
        self.base = base

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> FakeCommunicationConfig:
        enabled = bool(config.get("fakeCommunication", False))
        if not enabled:
            return cls(enabled=False)
        return cls(
            enabled=True,
            message_count=int(config.get("fakeMessageCount", 1)),
            base=config.get("fakeMessageBase", "dec"),
        )


class FakeMessageGenerator:
    """Generates fake communication messages for agents.

    Args:
        count: Number of fake messages emitted per call (>= 1).
        base: ``"dec"`` (0..999, three decimal digits max) or ``"hex"``
            (3-digit hex, ``"%03x"``).
        rng: Optional ``random.Random`` instance. When supplied, output is
            deterministic given the seed of that RNG. The default global
            ``random`` is used otherwise.
    """

    def __init__(
        self,
        count: int = 1,
        base: str = "dec",
        rng: random.Random | None = None,
    ) -> None:
        if base not in ("dec", "hex"):
            raise ValueError("base must be 'dec' or 'hex'")
        if count <= 0:
            raise ValueError("count must be a positive integer")

        self.count = count
        self.base = base
        self.rng = rng or random

    def _generate_one(self) -> str:
        value = self.rng.randint(0, 999)
        if self.base == "dec":
            return str(value)
        return format(value, "03x")

    def generate(self, agent, round_number: int) -> str:
        """Return one or more fake messages joined with ``", "``."""
        if self.count == 1:
            return self._generate_one()
        return ", ".join(self._generate_one() for _ in range(self.count))
