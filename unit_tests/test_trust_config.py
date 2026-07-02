"""Tests for the trust / costly-monitoring configuration object."""

from __future__ import annotations

import pytest

from src.trust import LOOK, NO_LOOK, TrustConfig


def test_disabled_by_default_when_no_block():
    cfg = TrustConfig.from_config({})
    assert cfg.enabled is False


def test_disabled_when_block_present_but_off():
    cfg = TrustConfig.from_config({"trust": {"enabled": False, "lookCost": 5}})
    assert cfg.enabled is False


def test_enabled_parses_fields():
    cfg = TrustConfig.from_config(
        {"trust": {"enabled": True, "lookCost": 0.25, "historyScope": "full"}}
    )
    assert cfg.enabled is True
    assert cfg.look_cost == 0.25
    assert cfg.history_scope == "full"


def test_enabled_accepts_string_true():
    cfg = TrustConfig.from_config({"trust": {"enabled": "True", "lookCost": 1}})
    assert cfg.enabled is True
    assert cfg.look_cost == 1.0


def test_negative_cost_rejected():
    with pytest.raises(ValueError):
        TrustConfig.from_config({"trust": {"enabled": True, "lookCost": -1}})


def test_unsupported_scope_rejected():
    with pytest.raises(ValueError):
        TrustConfig.from_config({"trust": {"enabled": True, "historyScope": "paid_last_n"}})


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("LOOK", LOOK),
        ("look", LOOK),
        ("I will LOOK at the history", LOOK),
        ("NO_LOOK", NO_LOOK),
        ("no look", NO_LOOK),
        ("NO LOOK please", NO_LOOK),
        ("", NO_LOOK),
        ("garbage", NO_LOOK),
    ],
)
def test_parse_action(raw, expected):
    assert TrustConfig.parse_action(raw) == expected
