"""Build a curated, parameter-complete starter library into the starter_library/ folder.

Reuses the canonical preset payoff matrices (proven) + resource template bodies,
sets distinct feature flags per configuration, structurally validates every
config, writes the starter_library/ JSON files, and loads the running store.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io_managers.configuration_validator import ConfigValidator  # noqa: E402
from src.utils.utils import get_resources_dir  # noqa: E402

_RESOURCES = get_resources_dir()
TPL = _RESOURCES / "game_templates"
CFG = _RESOURCES / "config"
from web_api.storage import load_store, save_store  # noqa: E402

NOW = "2026-01-01T00:00:00"


def main() -> None:
    """Build, validate, and write the starter library, then load the store.

    Guarded behind __main__ below: importing this module must never
    rewrite the live library or read machine-local store state.
    """

    def body(name):
        return (TPL / f"{name}.txt").read_text()

    def preset(rel):
        return json.loads((CFG / rel).read_text())

    # ---- Games (game types) -------------------------------------------------------
    GAMES = [
        ("gt_pd", "Prisoner's Dilemma", "The canonical social dilemma: cooperate or defect."),
        ("gt_stag", "Stag Hunt", "Coordination / assurance game."),
        ("gt_snowdrift", "Snow Drift", "Chicken / hawk-dove anti-coordination game."),
        ("gt_harmony", "Harmony Game", "No-conflict game where cooperation dominates."),
        ("gt_battle", "Battle of the Sexes", "Asymmetric coordination game."),
        ("gt_volunteer", "Volunteer's Dilemma", "N-player free-rider game."),
        ("gt_zerosum", "Zero-sum", "Strictly competitive game."),
    ]
    SEED_GAME_TYPES = [
        {"id": tid, "name": n, "description": d, "created_at": NOW} for tid, n, d in GAMES
    ]

    # ---- Templates ----------------------------------------------------------
    def tpl(game_type, variation, language, body_text, src_lang=None):
        return {
            "id": f"seed_tpl_{game_type}_{variation}_{language}",
            "game_type_id": game_type,
            "variation": variation,
            "language": language,
            "body": body_text,
            "source_template_id": None,
            "source_language": src_lang,
            "created_at": NOW,
            "updated_at": NOW,
            "versions": [],
            "archived": False,
        }

    # PD comm template body: reuse the one already in the running store if present.
    _store_tpls = {
        (t.get("game_type_id"), t.get("variation"), t.get("language")): t.get("body")
        for t in load_store("templates")
        if t.get("body")
    }
    pd_comm_body = _store_tpls.get(("gt_pd", "comm", "en")) or body("prisoner_dilemma_en")
    pd_covert_body = _store_tpls.get(("gt_pd", "covert", "en")) or body("prisoner_dilemma_en")

    SEED_TEMPLATES = [
        tpl("gt_pd", "conventional", "en", body("prisoner_dilemma_en")),
        tpl("gt_pd", "conventional", "fr", body("prisoner_dilemma_fr"), src_lang="en"),
        tpl("gt_pd", "tom", "en", body("prisoner_dilemma_tom_en")),
        tpl("gt_pd", "mixed", "en", body("prisoner_dilemma_mixed_en")),
        tpl("gt_pd", "trust", "en", body("prisoner_dilemma_trust_en")),
        tpl("gt_pd", "comm", "en", pd_comm_body),
        tpl("gt_pd", "covert", "en", pd_covert_body),
        tpl("gt_stag", "conventional", "en", body("stag_hunt_en")),
        tpl("gt_snowdrift", "conventional", "en", body("snow_drift_en")),
        tpl("gt_harmony", "conventional", "en", body("harmony_game_en")),
        tpl("gt_battle", "conventional", "en", body("battle_sexes_en")),
        tpl("gt_battle", "conventional", "fr", body("battle_sexes_fr"), src_lang="en"),
        tpl("gt_volunteer", "conventional", "en", body("volunteer_dilemma_en")),
        tpl("gt_zerosum", "conventional", "en", body("zero_sum_en")),
    ]

    # ---- Configuration game_config helpers ----------------------------------
    def base_gc(preset_rel, llms, *, agents_names=None, personalities=None, opp=None, **over):
        p = preset(preset_rel)
        gc = copy.deepcopy(p)
        for k in ("name", "languages", "templateFilename", "promptTemplate", "llm"):
            gc.pop(k, None)
        gc["llms"] = list(llms)
        a = gc.setdefault("agents", {})
        if agents_names is not None:
            a["names"] = list(agents_names)
        if personalities is not None:
            a["personalities"] = personalities
        if opp is not None:
            a["opponentPersonalityProb"] = opp
        gc.update(over)
        return gc

    # Configurations: (id, name, game_type, variation, languages, game_config, variations?)
    CONFIGS = []

    def add_cfg(cid, name, game_type, variation, langs, gc, variations=None):
        rec = {
            "id": cid,
            "name": name,
            "game_type_id": game_type,
            "variation": variation,
            "languages": langs,
            "game_config": gc,
            "created_at": NOW,
        }
        if variations is not None:
            rec["variations"] = variations
        CONFIGS.append(rec)

    PD = "prisoner_dilemma/prisoner_dilemma_round_known_conventional.json"
    PD_MILD = "prisoner_dilemma/prisoner_dilemma_round_known_mild.json"
    PD_HARSH = "prisoner_dilemma/prisoner_dilemma_round_known_harsh.json"
    PD_NK = "prisoner_dilemma/prisoner_dilemma_round_not_known_conventional.json"

    TWO = ["GPT-4o", "Claude Sonnet 4.6"]

    # 1. Baseline round-robin tournament (offline, no key)
    gc = base_gc(
        PD,
        [
            "baseline:TitForTat",
            "baseline:AlwaysCooperate",
            "baseline:AlwaysDefect",
            "baseline:GrimTrigger",
        ],
        agents_names=["agent1", "agent2", "agent3", "agent4"],
        personalities={"en": ["neutral"] * 4},
        opp=[0, 0, 0, 0],
        tournament={"enabled": True, "mode": "round_robin", "symmetric": True},
        baselineSemantics={"cooperate": "strategy1", "defect": "strategy2"},
    )
    add_cfg(
        "seed_cfg_pd_baseline_tournament",
        "PD — baseline round-robin tournament (offline)",
        "gt_pd",
        "conventional",
        ["en"],
        gc,
    )

    # 2. Plain LLM head-to-head
    add_cfg(
        "seed_cfg_pd_llm",
        "PD — LLM head-to-head",
        "gt_pd",
        "conventional",
        ["en"],
        base_gc(PD, TWO),
    )

    # 3. Real communication
    add_cfg(
        "seed_cfg_pd_comm",
        "PD — real communication",
        "gt_pd",
        "comm",
        ["en"],
        base_gc(PD, TWO, agentsCommunicate=True),
    )

    # 4. Covert signalling (fake hex decoy messages)
    add_cfg(
        "seed_cfg_pd_covert",
        "PD — covert signalling (hex decoy)",
        "gt_pd",
        "covert",
        ["en"],
        base_gc(PD, TWO, fakeCommunication=True, fakeMessageBase="hex", fakeMessageCount=10),
    )

    # 5. Theory of Mind + belief elicitation
    add_cfg(
        "seed_cfg_pd_tom",
        "PD — theory of mind + beliefs",
        "gt_pd",
        "tom",
        ["en"],
        base_gc(
            PD,
            TWO,
            personalities={"en": ["cooperative", "selfish"]},
            opp=[0.7, 0.7],
            elicitBeliefs=True,
            tomOrder=2,
        ),
    )

    # 6. Mixed strategies + multi-seed + auto equilibria
    add_cfg(
        "seed_cfg_pd_mixed",
        "PD — mixed strategies (multi-seed + equilibria)",
        "gt_pd",
        "mixed",
        ["en"],
        base_gc(
            PD,
            TWO,
            mixedStrategies=True,
            seedCount=3,
            seed=1,
            equilibria="auto",
            paretoOptimalSum=6,
        ),
    )

    # 7. Trust / costly monitoring
    add_cfg(
        "seed_cfg_pd_trust",
        "PD — trust / costly monitoring",
        "gt_pd",
        "trust",
        ["en"],
        base_gc(PD, TWO, trust={"enabled": True, "lookCost": 0.25, "historyScope": "full"}),
    )

    # 8. Inequity aversion (Fehr-Schmidt)
    add_cfg(
        "seed_cfg_pd_fehr",
        "PD — inequity aversion (Fehr-Schmidt)",
        "gt_pd",
        "conventional",
        ["en"],
        base_gc(PD, TWO, utilityTransform={"type": "FehrSchmidt", "alpha": 0.4, "beta": 0.6}),
    )

    # 9. Risk aversion (CRRA, prompt) + discount (prompt)
    add_cfg(
        "seed_cfg_pd_crra",
        "PD — risk aversion + discounting",
        "gt_pd",
        "conventional",
        ["en"],
        base_gc(
            PD,
            TWO,
            utilityTransform={"type": "CRRA", "gamma": 0.7, "offset": 1.0},
            riskMode="prompt",
            discountFactor=0.8,
            discountMode="prompt",
        ),
    )

    # 10. Personality pool permutations
    add_cfg(
        "seed_cfg_pd_pool",
        "PD — personality pool permutations",
        "gt_pd",
        "conventional",
        ["en"],
        base_gc(
            PD,
            TWO,
            allAgentPermutations=True,
            personalities={"en": ["cooperative", "selfish", "neutral"]},
            opp=[0, 0.5, 1],
        ),
    )

    # 11. Multilingual (EN + FR)
    gc = base_gc(
        PD, TWO, personalities={"en": ["cooperative", "selfish"], "fr": ["coopératif", "égoïste"]}
    )
    pm = gc["payoffMatrix"]
    pm["strategies"]["fr"] = dict(pm["strategies"]["en"])  # demo: copy labels
    add_cfg(
        "seed_cfg_pd_multilang",
        "PD — multilingual (EN + FR)",
        "gt_pd",
        "conventional",
        ["en", "fr"],
        gc,
    )

    # 12. Payoff sweep group (mild / harsh)
    gc = base_gc(PD, TWO)
    mild_pm = preset(PD_MILD)["payoffMatrix"]
    harsh_pm = preset(PD_HARSH)["payoffMatrix"]
    gc.pop("payoffMatrix", None)
    add_cfg(
        "seed_cfg_pd_sweep",
        "PD — payoff sweep (mild vs harsh)",
        "gt_pd",
        "conventional",
        ["en"],
        gc,
        variations=[
            {"axis": "payoffMatrix", "name": "mild", "value": mild_pm},
            {"axis": "payoffMatrix", "name": "harsh", "value": harsh_pm},
        ],
    )

    # 13. Uncertain horizon (continuation probability, rounds not known)
    add_cfg(
        "seed_cfg_pd_horizon",
        "PD — uncertain horizon",
        "gt_pd",
        "conventional",
        ["en"],
        base_gc(PD_NK, TWO, continuationProbability=0.85),
    )

    # 14. Stag Hunt
    add_cfg(
        "seed_cfg_stag",
        "Stag Hunt — coordination",
        "gt_stag",
        "conventional",
        ["en"],
        base_gc("stag_hunt/stag_hunt_round_known.json", TWO),
    )

    # 15. Snow Drift
    add_cfg(
        "seed_cfg_snowdrift",
        "Snow Drift — anti-coordination",
        "gt_snowdrift",
        "conventional",
        ["en"],
        base_gc("snow_drift/snow_drift_round_known.json", TWO),
    )

    # 16. Harmony
    add_cfg(
        "seed_cfg_harmony",
        "Harmony Game — dominant cooperation",
        "gt_harmony",
        "conventional",
        ["en"],
        base_gc("harmony_game/harmony_game_round_known.json", TWO),
    )

    # 17. Battle of the Sexes — multilingual + reputation off
    gc = base_gc("battle_sexes/battle_sexes_round_known_conventional.json", TWO)
    pm = gc["payoffMatrix"]
    if "fr" not in pm["strategies"]:
        pm["strategies"]["fr"] = dict(pm["strategies"]["en"])
    ap = gc.setdefault("agents", {}).setdefault("personalities", {})
    if "fr" not in ap and "en" in ap:
        ap["fr"] = list(ap["en"])
    gc["reputationApplies"] = False
    add_cfg(
        "seed_cfg_battle",
        "Battle of the Sexes — multilingual (EN+FR)",
        "gt_battle",
        "conventional",
        ["en", "fr"],
        gc,
    )

    # 18. Volunteer's Dilemma — n-player
    _vol = preset("volunteer_dilemma/volunteer_dilemma.json")
    _n = len(_vol.get("agents", {}).get("names", ["agent1", "agent2"]))
    gc = base_gc(
        "volunteer_dilemma/volunteer_dilemma.json", (TWO * _n)[:_n] if _n > 1 else ["GPT-4o"]
    )
    add_cfg(
        "seed_cfg_volunteer",
        "Volunteer's Dilemma — n-player",
        "gt_volunteer",
        "conventional",
        ["en"],
        gc,
    )

    # 19. Zero-sum — reputation off
    add_cfg(
        "seed_cfg_zerosum",
        "Zero-sum — strictly competitive",
        "gt_zerosum",
        "conventional",
        ["en"],
        base_gc("zero_sum/zero_sum_round_known.json", TWO, reputationApplies=False),
    )

    # 20. Interaction graph — asymmetric visibility + one-way messaging.
    # agent1 -> agent2 (talk): agent2 sees agent1's plays AND receives its messages.
    # agent2 -> agent1 (see):  agent1 only observes agent2's plays, no messages.
    gc = base_gc(PD, TWO, agents_names=["agent1", "agent2"], agentsCommunicate=True)
    gc["interaction"] = {
        "directed": True,
        "default": "none",
        "edges": [
            {"from": "agent1", "to": "agent2", "level": "talk"},
            {"from": "agent2", "to": "agent1", "level": "see"},
        ],
    }
    add_cfg(
        "seed_cfg_pd_interaction",
        "PD — interaction graph (asymmetric visibility)",
        "gt_pd",
        "comm",
        ["en"],
        gc,
    )

    # ---- Validate every configuration structurally --------------------------
    validator = ConfigValidator()
    errors = []
    for rec in CONFIGS:
        gc = copy.deepcopy(rec["game_config"])
        # For groups, inject the first variant matrix so the validator has one.
        if "payoffMatrix" not in gc and rec.get("variations"):
            gc["payoffMatrix"] = copy.deepcopy(rec["variations"][0]["value"])
        full = {
            **gc,
            "name": rec["name"],
            "languages": rec["languages"],
            "promptTemplate": {lang: "(validation placeholder)" for lang in rec["languages"]},
        }
        try:
            validator.validate_config_structure(full)
        except Exception as exc:  # noqa: BLE001
            errors.append((rec["id"], str(exc).splitlines()[0]))

    print(
        f"templates={len(SEED_TEMPLATES)} configs={len(CONFIGS)} game_types={len(SEED_GAME_TYPES)}"
    )
    if errors:
        print("VALIDATION ERRORS:")
        for cid, e in errors:
            print(f"  {cid}: {e}")
        sys.exit(1)
    print("ALL CONFIGS VALIDATED OK")

    # ---- Write the starter_library/ folder (the shipped source of truth) ----
    # One human-readable file per item, in three subfolders. Structured records
    # (game types, configurations) are pretty-printed JSON; templates are Markdown
    # with YAML frontmatter (metadata) + the raw, un-escaped prompt body. Files are
    # prefixed with a zero-padded index so the shipped order is preserved and the
    # loader (web_api/seeds.py) can restore it by sorting on filename.
    LIB = ROOT / "starter_library"
    LIB.mkdir(exist_ok=True)

    def _prefix(i, total):
        width = max(2, len(str(total)))
        return str(i + 1).zfill(width)

    def _reset_dir(name):
        d = LIB / name
        if d.exists():
            shutil.rmtree(d)  # drop stale items so removed seeds don't linger
        d.mkdir(parents=True)
        return d

    def _dump_json_items(name, items):
        d = _reset_dir(name)
        for i, item in enumerate(items):
            fname = f"{_prefix(i, len(items))}-{item['id']}.json"
            (d / fname).write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n")

    def _dump_templates(items):
        d = _reset_dir("templates")
        for i, tpl_item in enumerate(items):
            meta = {k: v for k, v in tpl_item.items() if k != "body"}
            front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
            fname = f"{_prefix(i, len(items))}-{tpl_item['id']}.md"
            (d / fname).write_text(f"---\n{front}---\n{tpl_item['body']}")

    # Remove the old consolidated files, if a previous build left them behind.
    for _old in ("game_types.json", "templates.json", "configurations.json"):
        (LIB / _old).unlink(missing_ok=True)

    _dump_json_items("game_types", SEED_GAME_TYPES)
    _dump_templates(SEED_TEMPLATES)
    _dump_json_items("configurations", CONFIGS)
    print(
        f"wrote starter_library/ ({len(SEED_GAME_TYPES)} game types, {len(SEED_TEMPLATES)} templates, {len(CONFIGS)} configs)"
    )
    print(
        "NOTE: README.md in starter_library/ is maintained separately; update it if the set changes."
    )

    # ---- Load into the running store so the change is visible immediately ----
    save_store("game_types", SEED_GAME_TYPES)
    save_store("templates", SEED_TEMPLATES)
    save_store("configurations", CONFIGS)
    print("store updated")


if __name__ == "__main__":
    main()
