"""Tests for configuration groups (variations on an axis).

A *leaf* configuration is the legacy shape: one ``game_config`` carrying a
``payoffMatrix`` directly. A *group* holds N variants under a named axis
(currently always ``payoffMatrix``) and resolves at run time to N
independent leaf configs. The display name of each resolved variant is
``"<group_name> · <variant_name>"``; saving must reject collisions
(against existing leaves or against any other group/variant pair) so
each runnable configuration carries a unique name.
"""

from __future__ import annotations

import unittest

from web_api.configurations_lib import (
    is_group,
    iter_resolved_variants,
    name_collisions,
    resolved_names,
)


def _leaf(name: str, matrix=None) -> dict:
    return {
        "id": f"id_{name}",
        "name": name,
        "game_type_id": "gt_pd",
        "variation": "classic",
        "languages": ["en"],
        "game_config": {"payoffMatrix": matrix or {"weights": {}}, "nRounds": 1},
    }


def _group(name: str, *variant_names: str) -> dict:
    return {
        "id": f"id_{name}",
        "name": name,
        "game_type_id": "gt_pd",
        "variation": "classic",
        "languages": ["en"],
        "game_config": {"nRounds": 1},
        "variations": [
            {"axis": "payoffMatrix", "name": v, "value": {"weights": {"w1": i}}}
            for i, v in enumerate(variant_names, start=1)
        ],
    }


class TestIsGroup(unittest.TestCase):
    def test_leaf_is_not_a_group(self) -> None:
        self.assertFalse(is_group(_leaf("PD-toy")))

    def test_item_with_variations_list_is_a_group(self) -> None:
        self.assertTrue(is_group(_group("PD-sweep", "mild", "harsh")))

    def test_empty_variations_list_is_not_a_group(self) -> None:
        # Defensive: an empty list shouldn't be treated as a group — a
        # group with zero variants would resolve to zero runnable configs.
        item = _group("PD-empty")
        item["variations"] = []
        self.assertFalse(is_group(item))


class TestResolvedNames(unittest.TestCase):
    def test_leaf_contributes_only_its_own_name(self) -> None:
        items = [_leaf("PD-toy"), _leaf("Stag")]
        self.assertEqual(resolved_names(items), {"PD-toy", "Stag"})

    def test_group_contributes_one_name_per_variant_with_separator(self) -> None:
        items = [_group("PD-sweep", "mild", "harsh", "classic")]
        self.assertEqual(
            resolved_names(items),
            {"PD-sweep · mild", "PD-sweep · harsh", "PD-sweep · classic"},
        )

    def test_mixed_library_resolves_all_names(self) -> None:
        items = [_leaf("Stag"), _group("PD-sweep", "mild", "harsh")]
        self.assertEqual(
            resolved_names(items),
            {"Stag", "PD-sweep · mild", "PD-sweep · harsh"},
        )


class TestNameCollisions(unittest.TestCase):
    def test_no_collisions_on_a_fresh_save(self) -> None:
        existing: list = []
        candidate = _leaf("PD-toy")
        self.assertEqual(name_collisions(existing, candidate), set())

    def test_leaf_collides_with_existing_leaf_of_same_name(self) -> None:
        existing = [_leaf("PD-toy")]
        candidate = _leaf("PD-toy")
        self.assertEqual(name_collisions(existing, candidate), {"PD-toy"})

    def test_leaf_collides_with_a_group_variant_of_same_resolved_name(self) -> None:
        # An existing group ``Sweep`` has variant ``one`` → resolved name
        # ``Sweep · one``. A new leaf literally named ``Sweep · one`` must
        # be rejected.
        existing = [_group("Sweep", "one", "two")]
        candidate = _leaf("Sweep · one")
        self.assertEqual(name_collisions(existing, candidate), {"Sweep · one"})

    def test_group_with_two_variants_colliding_with_two_leaves(self) -> None:
        existing = [_leaf("Sweep · mild"), _leaf("Sweep · harsh")]
        candidate = _group("Sweep", "mild", "harsh")
        self.assertEqual(
            name_collisions(existing, candidate),
            {"Sweep · mild", "Sweep · harsh"},
        )

    def test_self_update_is_not_a_collision(self) -> None:
        # Updating a saved item must not be flagged as colliding with
        # itself; the comparison excludes the candidate's own id.
        existing = [_leaf("PD-toy")]
        candidate = _leaf("PD-toy")
        candidate["id"] = existing[0]["id"]  # same id ⇒ this IS the update
        self.assertEqual(
            name_collisions(existing, candidate, exclude_id=candidate["id"]),
            set(),
        )

    def test_group_with_internal_duplicate_variant_name(self) -> None:
        # Two variants in the same group sharing a name resolve to the
        # same display name → a collision in their own right.
        item = _group("Sweep", "mild", "mild")
        self.assertEqual(name_collisions([], item), {"Sweep · mild"})


class TestIterResolvedVariants(unittest.TestCase):
    def test_leaf_yields_one_variant_with_full_engine_config(self) -> None:
        leaf = _leaf("PD-toy", matrix={"weights": {"w1": 3}})
        out = list(iter_resolved_variants(leaf))
        self.assertEqual(len(out), 1)
        variant = out[0]
        self.assertIsNone(variant.variant_name)  # leaf: no variant identity
        self.assertEqual(variant.display_name, "PD-toy")
        self.assertEqual(variant.config["payoffMatrix"], {"weights": {"w1": 3}})
        self.assertEqual(variant.config["nRounds"], 1)

    def test_group_yields_one_variant_per_entry_with_axis_value_applied(self) -> None:
        group = _group("Sweep", "mild", "harsh")
        out = {v.variant_name: v for v in iter_resolved_variants(group)}
        self.assertEqual(set(out), {"mild", "harsh"})
        # Display names carry the group prefix; variant identity stays bare.
        self.assertEqual(out["mild"].display_name, "Sweep · mild")
        # Each resolved cfg gets the variant's value placed on its axis.
        self.assertEqual(out["mild"].config["payoffMatrix"], {"weights": {"w1": 1}})
        self.assertEqual(out["harsh"].config["payoffMatrix"], {"weights": {"w1": 2}})
        # Untouched fields survive on every resolved variant.
        self.assertEqual(out["mild"].config["nRounds"], 1)

    def test_resolved_variants_are_independent_copies(self) -> None:
        # Mutating one resolved cfg must not bleed into the other (the
        # group is the source of truth; resolution must deep-copy).
        group = _group("Sweep", "mild", "harsh")
        out = {v.variant_name: v for v in iter_resolved_variants(group)}
        out["mild"].config["payoffMatrix"]["weights"]["w1"] = 999
        self.assertEqual(out["harsh"].config["payoffMatrix"]["weights"]["w1"], 2)

    def test_unknown_axis_raises(self) -> None:
        # The current axis allow-list is just ``payoffMatrix``. An
        # unknown axis is a configuration error: we'd silently produce
        # an unrunnable config otherwise.
        group = _group("Sweep", "mild")
        group["variations"][0]["axis"] = "nonsense"
        with self.assertRaises(ValueError):
            list(iter_resolved_variants(group))


if __name__ == "__main__":
    unittest.main()
