"""Catalog of shipped scenarios surfaced in the GUI.

Each preset wraps a config file under ``resources/config/`` (or
``unit_tests/config/``) with a friendly name, description, and the set of
features it exercises (used to render the colour-coded pill tags).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ScenarioPreset:
    """Metadata + path for one shipped scenario."""

    key: str
    name: str
    summary: str
    config_path: Path
    tags: List[str] = field(default_factory=list)
    template_hint: str = "prisoner_dilemma"

    def load(self) -> Dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as fh:
            config = json.load(fh)
        # Some shipped configs leave the template binding to the CLI (it injects
        # ``promptTemplate`` at runtime). The GUI runner doesn't have that
        # luxury, so fill in a reasonable templateFilename if neither pointer
        # is set.
        if "promptTemplate" not in config and "templateFilename" not in config:
            config["templateFilename"] = self.template_hint
        return config


CATALOG: List[ScenarioPreset] = [
    ScenarioPreset(
        key="pd_classic",
        name="Prisoner's Dilemma — classic",
        summary=(
            "The canonical 2-player one-shot Prisoner's Dilemma in five "
            "languages. A good first run to verify everything works."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "prisoner_dilemma"
        / "prisoner_dilemma_round_known_conventional.json",
        tags=["Two-player", "Multilingual"],
    ),
    ScenarioPreset(
        key="pd_tom",
        name="Prisoner's Dilemma — Theory of Mind",
        summary=(
            "Adds belief elicitation, second-order ToM, and a private type "
            "system. Brier-score columns appear in the results."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "prisoner_dilemma_tom"
        / "prisoner_dilemma_tom.json",
        tags=["ToM", "Belief elicitation", "Types"],
    ),
    ScenarioPreset(
        key="pd_mixed",
        name="Prisoner's Dilemma — mixed strategies + discount",
        summary=(
            "The agent emits a probability distribution per round; the engine "
            "samples. Includes a δ=0.9 discount factor and Pareto-efficiency "
            "metric."
        ),
        config_path=ROOT / "unit_tests" / "config" / "prisoner_dilemma_mixed.json",
        tags=["Mixed strategies", "Discount factor", "Equilibria"],
    ),
    ScenarioPreset(
        key="pd_tournament",
        name="Round-robin tournament",
        summary=(
            "AlwaysCooperate vs AlwaysDefect vs TitForTat in a round-robin. "
            "Demonstrates the canonical baseline strategy library."
        ),
        config_path=ROOT
        / "unit_tests"
        / "config"
        / "prisoner_dilemma_tournament.json",
        tags=["Tournament", "Baselines"],
    ),
    ScenarioPreset(
        key="volunteer",
        name="Volunteer's Dilemma — multi-agent",
        summary=(
            "Three agents, two-strategy each, with a 2-personality pool. "
            "Stress-tests the permutation generator."
        ),
        config_path=ROOT
        / "unit_tests"
        / "config"
        / "volunteer_dilemma_multiple_games.json",
        tags=["N-player", "Permutations"],
        template_hint="volunteer_dilemma",
    ),
    # ---- 2x2 social-dilemma family ported from Fairgame_paper_evaluations ----
    ScenarioPreset(
        key="stag_hunt",
        name="Stag Hunt",
        summary=(
            "Two pure-strategy Nash equilibria — joint hunt (payoff-dominant) "
            "vs joint hare (risk-dominant). The classic coordination dilemma."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "stag_hunt"
        / "stag_hunt_round_known.json",
        tags=["Coordination", "Two equilibria"],
        template_hint="stag_hunt",
    ),
    ScenarioPreset(
        key="snow_drift",
        name="Snowdrift (Chicken)",
        summary=(
            "Asymmetric anti-coordination: each player wants the other to "
            "shovel. Two pure-strategy equilibria at the off-diagonal cells."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "snow_drift"
        / "snow_drift_round_known.json",
        tags=["Anti-coordination", "Chicken"],
        template_hint="snow_drift",
    ),
    ScenarioPreset(
        key="harmony_game",
        name="Harmony Game",
        summary=(
            "Cooperation strictly dominates defection. The benign benchmark "
            "against which the other social dilemmas can be compared."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "harmony_game"
        / "harmony_game_round_known.json",
        tags=["No conflict", "Dominance"],
        template_hint="harmony_game",
    ),
    ScenarioPreset(
        key="battle_sexes",
        name="Battle of the Sexes",
        summary=(
            "Asymmetric coordination: each agent prefers a different "
            "equilibrium but coordination beats miscoordination for both."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "battle_sexes"
        / "battle_sexes_round_known.json",
        tags=["Asymmetric", "Coordination"],
        template_hint="battle_sexes",
    ),
    ScenarioPreset(
        key="zero_sum",
        name="Zero-Sum Matching",
        summary=(
            "Strictly competitive: one player's gain is the other's loss. "
            "The unique equilibrium is in mixed strategies."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "zero_sum"
        / "zero_sum_round_known.json",
        tags=["Zero-sum", "Mixed equilibrium"],
        template_hint="zero_sum",
    ),
    # ---- Covert-communication family ----------------------------------
    ScenarioPreset(
        key="pd_covert_dec",
        name="Prisoner's Dilemma — covert decimal channel",
        summary=(
            "Agents communicate, but the channel is restricted to a sequence "
            "of 10 decimal numbers per round. Studies whether they can "
            "smuggle strategy information through a covert channel."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "prisoner_dilemma"
        / "covert"
        / "prisoner_dilemma_covert_dec.json",
        tags=["Covert channel", "Communication"],
        template_hint="prisoner_dilemma_covert_dec",
    ),
    ScenarioPreset(
        key="pd_covert_hex",
        name="Prisoner's Dilemma — covert hex channel",
        summary=(
            "Same as covert decimal but the agents must encode their messages "
            "as 10 hexadecimal numbers. Tighter information channel."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "prisoner_dilemma"
        / "covert"
        / "prisoner_dilemma_covert_hex.json",
        tags=["Covert channel", "Hex"],
        template_hint="prisoner_dilemma_covert_hex",
    ),
    ScenarioPreset(
        key="pd_random_dec",
        name="Prisoner's Dilemma — random decimal control",
        summary=(
            "Control: agents are explicitly *told* to output a random "
            "10-number sequence. Compare against the covert variant to "
            "isolate any signalling effect."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "prisoner_dilemma"
        / "covert"
        / "prisoner_dilemma_random_dec.json",
        tags=["Control", "Random channel"],
        template_hint="prisoner_dilemma_random_dec",
    ),
    ScenarioPreset(
        key="pd_fake_dec",
        name="Prisoner's Dilemma — fake decimal channel",
        summary=(
            "The engine generates the 10-number sequence on the agents' "
            "behalf. Acts as a hard floor — any signal in covert/random above "
            "this is real."
        ),
        config_path=ROOT
        / "resources"
        / "config"
        / "prisoner_dilemma"
        / "covert"
        / "prisoner_dilemma_fake_dec.json",
        tags=["Fake channel", "Engine-generated"],
        template_hint="prisoner_dilemma",
    ),
]


def by_key(key: str) -> ScenarioPreset:
    for preset in CATALOG:
        if preset.key == key:
            return preset
    raise KeyError(key)


def usable_presets() -> List[ScenarioPreset]:
    """Return only presets whose underlying config file actually exists."""
    return [p for p in CATALOG if p.config_path.is_file()]
