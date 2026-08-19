"""Configuration-group helpers.

A *leaf* configuration is the legacy shape: ``game_config`` carries
everything (including ``payoffMatrix``). A *group* moves one or more
fields out into a list of named ``variations`` along a named axis, and
resolves at run time to one independent leaf per variant.

The display name of a resolved variant is ``"<group> · <variant>"`` (the
separator is ``" · "`` — U+00B7). Saving must enforce that every
resolved name across the whole library is unique.

For now the only allowed axis is ``payoffMatrix`` — the schema is
deliberately general so a follow-up can add ``nRounds``, ``tomOrder``,
etc. without another migration.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Iterator
from typing import Any, NamedTuple

NAME_SEPARATOR = " · "
ALLOWED_AXES = ("payoffMatrix",)


class ResolvedVariant(NamedTuple):
    """One runnable unit of a configuration.

    ``variant_name`` is the bare variant name (``None`` for a leaf) — the
    stable identity used to select a variant. ``display_name`` is the
    human-facing ``"<group> · <variant>"`` label (just the config name for a
    leaf); it is presentation only and never parsed back apart.
    """

    variant_name: str | None
    display_name: str
    config: dict[str, Any]


def is_group(item: dict[str, Any]) -> bool:
    """``True`` iff ``item`` carries at least one variation."""
    return bool(item.get("variations"))


def iter_resolved_variants(item: dict[str, Any]) -> Iterator[ResolvedVariant]:
    """Yield one :class:`ResolvedVariant` per runnable variant.

    For a leaf, exactly one. For a group, one per entry in ``variations``;
    each resolved config is a deep copy of ``game_config`` with the variant's
    value placed on its declared axis.
    """
    base_cfg = item.get("game_config") or {}
    # Tolerate a malformed stored config: fall back to the id (or a sentinel)
    # rather than raising a raw KeyError that surfaces as a 500.
    item_name = item.get("name") or item.get("id") or "(unnamed)"
    if not is_group(item):
        yield ResolvedVariant(None, item_name, copy.deepcopy(base_cfg))
        return
    for variation in item.get("variations") or []:
        axis = variation.get("axis")
        if axis not in ALLOWED_AXES:
            raise ValueError(f"Unknown variation axis {axis!r}; allowed: {ALLOWED_AXES}")
        resolved = copy.deepcopy(base_cfg)
        resolved[axis] = copy.deepcopy(variation.get("value"))
        variation_name = variation.get("name") or "(unnamed)"
        yield ResolvedVariant(
            variation_name,
            f"{item_name}{NAME_SEPARATOR}{variation_name}",
            resolved,
        )


def resolved_names(items: Iterable[dict[str, Any]]) -> set[str]:
    """All currently-runnable display names in the library."""
    out: set[str] = set()
    for item in items:
        for variant in iter_resolved_variants(item):
            out.add(variant.display_name)
    return out


def name_collisions(
    existing: Iterable[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    exclude_id: str | None = None,
) -> set[str]:
    """Names the candidate would create that already exist in ``existing``.

    Pass ``exclude_id`` when validating an update so the candidate
    doesn't collide with the version of itself being replaced.

    Internal duplicate variant names within ``candidate`` are also
    flagged: two variants resolving to the same display name would
    create two un-distinguishable runs.
    """
    others = [i for i in existing if i.get("id") != exclude_id]
    occupied: set[str] = set()
    for item in others:
        for variant in iter_resolved_variants(item):
            occupied.add(variant.display_name)

    collisions: set[str] = set()
    seen_in_candidate: set[str] = set()
    for variant in iter_resolved_variants(candidate):
        if variant.display_name in occupied or variant.display_name in seen_in_candidate:
            collisions.add(variant.display_name)
        seen_in_candidate.add(variant.display_name)
    return collisions
