"""Parse and normalise belief responses elicited from LLM agents.

A belief is a probability distribution over the opponent's strategies. The
agent is asked to reply with JSON of the form ``{"label": prob, ...}``, but
LLMs frequently wrap the JSON in prose. The parser:

* Extracts the first JSON object from the response.
* Maps strategy display labels back to canonical strategy keys.
* Coerces probabilities to floats and re-normalises if they sum to ~1 within
  a tolerance, otherwise raises ``BeliefParseError``.
"""

from __future__ import annotations

import json
from typing import Dict, Mapping

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BeliefParseError(ValueError):
    """Raised when an LLM belief response cannot be parsed into a distribution."""


def _extract_json_blob(text: str) -> str:
    """Return the substring from the first ``{`` to its matching ``}``.

    Brace-balanced extraction so prose containing stray ``}`` characters
    after the JSON block (e.g. ``"...} . Hope this helps."``) does not
    confuse the parser.
    """
    start = text.find("{")
    if start == -1:
        raise BeliefParseError("No JSON object found in belief response.")
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise BeliefParseError("Unterminated JSON object in belief response.")


def parse_belief(
    response: str,
    strategies: Mapping[str, str],
    *,
    sum_tolerance: float = 0.05,
) -> Dict[str, float]:
    """Parse a belief response into ``{strategy_key: probability}``.

    Args:
        response: The raw text returned by the LLM.
        strategies: Mapping of canonical strategy keys to display labels (the
            same dict used in the payoff matrix for the game's language).
        sum_tolerance: Acceptable deviation from 1.0 in the parsed sum before
            re-normalisation kicks in. Sums outside ``[1 - 5*tolerance,
            1 + 5*tolerance]`` are rejected outright.

    Returns:
        A normalised distribution keyed by strategy *key* (not display label).

    Raises:
        BeliefParseError: when the response is unparseable or the
            distribution is too far from a probability vector to recover.
    """
    if not isinstance(response, str) or not response.strip():
        raise BeliefParseError("Belief response is empty.")

    blob = _extract_json_blob(response)
    try:
        raw: Dict[str, object] = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise BeliefParseError(f"Invalid JSON in belief response: {exc}") from exc

    if not isinstance(raw, dict) or not raw:
        raise BeliefParseError("Belief response must be a non-empty JSON object.")

    label_to_key = {label.lower(): key for key, label in strategies.items()}
    key_to_label = dict(strategies)

    distribution: Dict[str, float] = {}
    for raw_key, raw_value in raw.items():
        try:
            probability = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise BeliefParseError(
                f"Probability for {raw_key!r} is not numeric: {raw_value!r}"
            ) from exc
        if probability < 0:
            raise BeliefParseError(f"Negative probability for {raw_key!r}.")

        canonical = _resolve_strategy(raw_key, label_to_key, key_to_label)
        if canonical is None:
            logger.debug("Discarding unknown strategy key %r in belief response.", raw_key)
            continue
        # Last-write-wins if the LLM names the same strategy twice.
        distribution[canonical] = probability

    if not distribution:
        raise BeliefParseError("Belief response did not reference any known strategy.")

    total = sum(distribution.values())
    if total <= 0:
        raise BeliefParseError("Belief probabilities sum to zero.")

    if abs(total - 1.0) > 5 * sum_tolerance:
        raise BeliefParseError(
            f"Belief probabilities sum to {total:.3f}, expected ~1.0."
        )

    if abs(total - 1.0) > sum_tolerance:
        logger.debug("Re-normalising belief distribution from sum=%.3f", total)

    normalised = {key: prob / total for key, prob in distribution.items()}

    # Fill in zero-probability entries for strategies the agent omitted.
    for key in strategies:
        normalised.setdefault(key, 0.0)

    return normalised


def _resolve_strategy(
    raw_key: str,
    label_to_key: Mapping[str, str],
    key_to_label: Mapping[str, str],
) -> str | None:
    """Map an LLM-supplied key back to a canonical strategy key.

    Accepts either canonical keys ("strategy1") or display labels ("Cooperate").
    Matching is case-insensitive on display labels.
    """
    lowered = raw_key.lower()
    if raw_key in key_to_label:
        return raw_key
    if lowered in label_to_key:
        return label_to_key[lowered]
    return None
