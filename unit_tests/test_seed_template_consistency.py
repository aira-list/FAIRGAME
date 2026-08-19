"""Every shipped seed configuration's resolved prompt template must actually
implement what the configuration's variation / enabled features claim.

These are static (no engine, no LLM) invariants over ``starter_library/``:
a seed that says it uses real communication must give the agent a
``{communicate}`` block, no two distinct variations may ship the *same*
template body (the copy-paste smell that shipped ``comm``/``covert`` as
verbatim clones of ``conventional``), and any behavioural block a template
carries must be reachable by at least one configuration that binds to it.
"""

from __future__ import annotations

import re
import unittest

from web_api.library_service import find_template
from web_api.seeds import SEED_CONFIGURATIONS, SEED_TEMPLATES


def _has_block(body: str, name: str) -> bool:
    """True if ``body`` contains a ``{name}: [ ... ]`` phase/optional block."""
    return re.search(rf"\{{{name}\}}\s*:\s*\[", body) is not None


def _resolved_templates(cfg):
    """Every (language, template) pair a non-baseline config binds to."""
    gc = cfg.get("game_config", {})
    llms = gc.get("llms") or gc.get("llm")
    models = llms if isinstance(llms, list) else [llms] if llms else []
    if models and all(isinstance(m, str) and m.startswith("baseline:") for m in models):
        return []  # baseline-only: the prompt is never read
    out = []
    for lang in cfg.get("languages") or ["en"]:
        tpl = find_template(SEED_TEMPLATES, cfg["game_type_id"], cfg["variation"], lang)
        out.append((lang, tpl))
    return out


class TestSeedTemplateConsistency(unittest.TestCase):
    def test_every_config_resolves_a_template(self):
        for cfg in SEED_CONFIGURATIONS:
            for lang, tpl in _resolved_templates(cfg):
                self.assertIsNotNone(
                    tpl,
                    f"{cfg['id']}: no template for "
                    f"({cfg['game_type_id']}, {cfg['variation']}, {lang})",
                )

    def test_no_two_templates_share_a_body(self):
        by_body: dict[str, list[str]] = {}
        for t in SEED_TEMPLATES:
            if t.get("archived"):
                continue
            by_body.setdefault(t["body"].strip(), []).append(t["id"])
        dupes = {body[:40]: ids for body, ids in by_body.items() if len(ids) > 1}
        self.assertEqual(
            dupes, {}, f"distinct templates ship an identical body (copy-paste): {dupes}"
        )

    def test_real_communication_configs_have_a_communicate_block(self):
        for cfg in SEED_CONFIGURATIONS:
            if not cfg.get("game_config", {}).get("agentsCommunicate"):
                continue
            for lang, tpl in _resolved_templates(cfg):
                self.assertIsNotNone(tpl, f"{cfg['id']}: missing template ({lang})")
                self.assertTrue(
                    _has_block(tpl["body"], "communicate"),
                    f"{cfg['id']} claims real communication but its {lang} template "
                    f"{tpl['id']} has no {{communicate}} block",
                )
                self.assertNotIn(
                    "cannot communicate",
                    tpl["body"].lower(),
                    f"{cfg['id']} enables communication yet {tpl['id']} tells the "
                    f"agent it cannot communicate",
                )

    def test_prompt_mode_behavioural_configs_have_their_blocks(self):
        """riskMode/discountMode == 'prompt' means the framing is spoken to the
        agent, so the resolved template must carry the matching block."""
        for cfg in SEED_CONFIGURATIONS:
            ut = cfg.get("game_config", {}).get("utilityTransform") or {}
            wants = set()
            if ut.get("riskMode") == "prompt":
                wants.add("riskFrame")
            if ut.get("discountMode") == "prompt":
                wants.add("discount")
            if not wants:
                continue
            for lang, tpl in _resolved_templates(cfg):
                self.assertIsNotNone(tpl, f"{cfg['id']}: missing template ({lang})")
                for block in wants:
                    self.assertTrue(
                        _has_block(tpl["body"], block),
                        f"{cfg['id']} speaks {block} to the agent but {tpl['id']} "
                        f"has no {{{block}}} block",
                    )


if __name__ == "__main__":
    unittest.main()
