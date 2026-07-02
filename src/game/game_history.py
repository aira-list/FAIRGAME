from __future__ import annotations

from typing import Any

from src.utils.utils import round_index

# One round's records, keyed by agent name; each agent maps field name -> value.
RoundData = dict[str, dict[str, Any]]


class GameHistory:
    """Round-by-round history, stored as a ``{round_key: {agent: {field: value}}}`` dict."""

    # Audit-only fields recorded for results/output but NEVER fed back into a
    # prompt. They hold full rendered prompts, which themselves embed the
    # ``{history}`` placeholder; echoing them into the next round's prompt
    # re-embeds all prior prompts and makes the history grow exponentially
    # (a 5-round ToM-2 game ballooned to ~21 GB). See ``prompt_view``.
    _PROMPT_ONLY_FIELDS = ("belief_prompt", "belief_2nd_order_prompt")

    def __init__(self) -> None:
        self.rounds: dict[str, RoundData] = {}

    def update_round(self, round_number: int, agent_name: str, data: dict[str, Any]) -> None:
        """Merge ``data`` into the record for ``agent_name`` in the given round."""
        round_key = f"round_{round_number}"
        if round_key not in self.rounds:
            self.rounds[round_key] = {}
        self.rounds[round_key].setdefault(agent_name, {}).update(data)

    def prompt_view(self) -> dict[str, RoundData]:
        """Return a history view safe to embed in a prompt via ``{history}``.

        Excludes the bulky ``*_prompt`` audit fields (see
        :attr:`_PROMPT_ONLY_FIELDS`) so rendering the history into a new
        prompt never re-embeds prior prompts — which would grow the history
        exponentially round over round. The underlying :attr:`rounds` is not
        mutated; ``describe()`` still exposes the full record for output.
        """
        return {
            round_key: {
                agent_name: {k: v for k, v in data.items() if k not in self._PROMPT_ONLY_FIELDS}
                for agent_name, data in agents_data.items()
            }
            for round_key, agents_data in self.rounds.items()
        }

    @property
    def all_rounds(self) -> dict[str, RoundData]:
        """All round data stored so far."""
        return self.rounds

    def __str__(self) -> str:
        return str(self.rounds)

    def describe(self) -> dict[str, list[dict[str, Any]]]:
        """Return an ordered, round-keyed summary.

        Keys are round strings (``'round_1'``, ``'round_2'``, ...) in numeric
        order; each value is a list of per-agent record dicts.
        """
        summary: dict[str, list[dict[str, Any]]] = {}

        # Sort round keys by the numeric part to ensure correct ordering
        sorted_round_keys = sorted(self.rounds.keys(), key=round_index)

        for round_key in sorted_round_keys:
            agents_data = self.rounds[round_key]
            round_list: list[dict[str, Any]] = []

            for agent_name, data in agents_data.items():
                round_list.append(
                    {
                        "agent": agent_name,
                        "message": data.get("message"),
                        "strategy": data.get("strategy"),
                        "score": data.get("score"),
                        "belief": data.get("belief"),
                        "belief_prompt": data.get("belief_prompt"),
                        "belief_2nd_order": data.get("belief_2nd_order"),
                        "belief_2nd_order_prompt": data.get("belief_2nd_order_prompt"),
                        "mixed_distribution": data.get("mixed_distribution"),
                        "trust_action": data.get("trust_action"),
                        "trust_cost": data.get("trust_cost"),
                    }
                )

            summary[round_key] = round_list

        return summary
