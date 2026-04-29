"""Reusable Streamlit form widgets for editing FAIRGAME configs.

These helpers take a config dict by reference and return the (possibly
edited) version. The callers compose them inside ``st.form`` blocks; we
deliberately keep them stateless so each tab can render the same widget
without leaking values across pages.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from src.llm_connectors import MODEL_PROVIDER_MAP

_BASELINE_CHOICES = [
    "Baseline:AlwaysCooperate",
    "Baseline:AlwaysDefect",
    "Baseline:Random",
    "Baseline:TitForTat",
    "Baseline:GrimTrigger",
]


def llm_choices() -> List[str]:
    """All selectable model identifiers — registered LLMs + canonical baselines."""
    return sorted(set(MODEL_PROVIDER_MAP.keys())) + _BASELINE_CHOICES


def basics_form(config: Dict[str, Any]) -> Dict[str, Any]:
    """Edit name, rounds, languages, fake-comm flag."""
    cols = st.columns([2, 1, 1])
    config["name"] = cols[0].text_input(
        "Scenario name",
        value=config.get("name", "Untitled scenario"),
        help="Used in result filenames and logs.",
    )
    config["nRounds"] = int(
        cols[1].number_input(
            "Rounds",
            min_value=1,
            max_value=200,
            value=int(config.get("nRounds", 1)),
            step=1,
        )
    )
    config["nRoundsIsKnown"] = cols[2].checkbox(
        "Tell agents the round count",
        value=bool(config.get("nRoundsIsKnown", True)),
    )

    languages_default = ", ".join(config.get("languages", ["en"]))
    raw_langs = st.text_input(
        "Languages (comma-separated BCP-47 codes)",
        value=languages_default,
        help="Each language must have entries in agents.personalities and payoffMatrix.strategies.",
    )
    config["languages"] = [s.strip() for s in raw_langs.split(",") if s.strip()]

    cols2 = st.columns(2)
    config["agentsCommunicate"] = cols2[0].checkbox(
        "Allow inter-agent communication",
        value=bool(config.get("agentsCommunicate", False)),
    )
    config["allAgentPermutations"] = cols2[1].checkbox(
        "Run all personality permutations",
        value=bool(config.get("allAgentPermutations", True)),
        help=(
            "When on, expand all personality / opponent-prior combinations. "
            "Symmetric pairs are deduplicated when every agent uses the same LLM."
        ),
    )
    return config


def agents_form(config: Dict[str, Any]) -> Dict[str, Any]:
    """Edit the agent roster: names, personalities (per language), priors, LLM."""
    agents = dict(config.get("agents") or {})
    languages: List[str] = config.get("languages", ["en"])

    n_agents = st.number_input(
        "Number of agents",
        min_value=2,
        max_value=8,
        value=len(agents.get("names", ["agent1", "agent2"])),
        step=1,
        help="Most classical games are 2-player; multi-agent setups expand permutations rapidly.",
    )

    # Resize lists to the requested count, padding with sensible defaults.
    names: List[str] = list(agents.get("names", []))
    while len(names) < n_agents:
        names.append(f"agent{len(names) + 1}")
    names = names[:n_agents]

    personalities = dict(agents.get("personalities", {}))
    for lang in languages:
        plist = list(personalities.get(lang, []))
        while len(plist) < n_agents:
            plist.append("cooperative")
        personalities[lang] = plist[:n_agents]

    probs = list(agents.get("opponentPersonalityProb", []))
    while len(probs) < n_agents:
        probs.append(0)
    probs = probs[:n_agents]

    options = llm_choices()
    llms_dict: Dict[str, str] = (
        dict(config.get("llms")) if isinstance(config.get("llms"), dict) else {}
    )
    fallback_llm = config.get("llm") or (options[0] if options else "")

    edited_names: List[str] = []
    edited_probs: List[float] = []
    edited_llms: Dict[str, str] = {}
    edited_personalities: Dict[str, List[str]] = {lang: [] for lang in languages}

    for i in range(n_agents):
        with st.expander(f"Agent {i + 1}", expanded=(i < 2)):
            c1, c2, c3 = st.columns([1, 1, 1])
            new_name = c1.text_input(
                "Name", value=names[i], key=f"agent_name_{i}"
            ).strip() or f"agent{i + 1}"
            edited_names.append(new_name)
            edited_probs.append(
                float(
                    c2.number_input(
                        "Opponent-cooperative prior (%)",
                        min_value=0,
                        max_value=100,
                        value=int(probs[i]),
                        key=f"agent_prob_{i}",
                    )
                )
            )
            current_llm = llms_dict.get(names[i], fallback_llm)
            llm_idx = options.index(current_llm) if current_llm in options else 0
            edited_llms[new_name] = c3.selectbox(
                "Model / strategy",
                options=options,
                index=llm_idx,
                key=f"agent_llm_{i}",
            )

            for lang in languages:
                edited_personalities[lang].append(
                    st.text_input(
                        f"Personality ({lang})",
                        value=personalities[lang][i],
                        key=f"agent_pers_{lang}_{i}",
                    )
                )

    agents["names"] = edited_names
    agents["personalities"] = edited_personalities
    agents["opponentPersonalityProb"] = edited_probs
    config["agents"] = agents

    # Use the per-agent dict form so mixed-LLM tournaments work cleanly.
    config["llms"] = edited_llms
    config.pop("llm", None)
    return config


def tom_form(config: Dict[str, Any]) -> Dict[str, Any]:
    cols = st.columns(2)
    config["elicitBeliefs"] = cols[0].checkbox(
        "Elicit per-round beliefs (JSON)",
        value=bool(config.get("elicitBeliefs", False)),
    )
    config["tomOrder"] = int(
        cols[1].select_slider(
            "Theory-of-Mind order",
            options=[0, 1, 2],
            value=int(config.get("tomOrder", 1)),
            help=(
                "0: opponent info hidden. "
                "1: opponent personality + prior visible (default). "
                "2: also enable {secondOrder} block."
            ),
        )
    )

    use_types = st.checkbox(
        "Add a Bayesian-game type system",
        value=bool(config.get("agents", {}).get("types")),
    )
    if use_types:
        types_block = config.get("agents", {}).get("types") or {
            "labels": ["trusting", "cynical"],
            "probs": [0.5, 0.5],
            "commonKnowledge": False,
        }
        labels = st.text_input(
            "Type labels (comma-separated)",
            value=", ".join(types_block.get("labels", [])),
        )
        labels_list = [s.strip() for s in labels.split(",") if s.strip()]
        probs_str = st.text_input(
            "Probabilities (comma-separated, will be re-normalised)",
            value=", ".join(str(p) for p in types_block.get("probs", [])),
        )
        try:
            probs_list = [float(s.strip()) for s in probs_str.split(",") if s.strip()]
        except ValueError:
            st.warning("Probabilities must be numeric; falling back to uniform.")
            probs_list = [1 / max(1, len(labels_list))] * len(labels_list)
        common_knowledge = st.checkbox(
            "Type prior is common knowledge",
            value=bool(types_block.get("commonKnowledge", False)),
        )
        config.setdefault("agents", {})["types"] = {
            "labels": labels_list,
            "probs": probs_list,
            "commonKnowledge": common_knowledge,
        }
        config["typesAreCommonKnowledge"] = common_knowledge
    else:
        config.setdefault("agents", {}).pop("types", None)
        config.pop("typesAreCommonKnowledge", None)
    return config


def game_theory_form(config: Dict[str, Any]) -> Dict[str, Any]:
    cols = st.columns(2)
    config["mixedStrategies"] = cols[0].checkbox(
        "Mixed strategies",
        value=bool(config.get("mixedStrategies", False)),
        help="Agent emits a JSON probability distribution; engine samples.",
    )
    config["discountFactor"] = float(
        cols[1].slider(
            "Discount factor δ",
            min_value=0.10,
            max_value=1.00,
            value=float(config.get("discountFactor", 1.0)),
            step=0.05,
        )
    )
    use_continuation = st.checkbox(
        "Indefinite horizon (per-round termination probability)",
        value=config.get("continuationProbability") is not None,
    )
    if use_continuation:
        config["continuationProbability"] = float(
            st.slider(
                "Continuation probability",
                min_value=0.05,
                max_value=1.00,
                value=float(config.get("continuationProbability") or 0.95),
                step=0.05,
            )
        )
    else:
        config.pop("continuationProbability", None)

    transform = st.selectbox(
        "Utility transform",
        options=["identity", "CRRA", "FehrSchmidt"],
        index=["identity", "CRRA", "FehrSchmidt"].index(
            (config.get("utilityTransform") or {}).get("type", "identity")
        ),
    )
    if transform == "identity":
        config.pop("utilityTransform", None)
    elif transform == "CRRA":
        gamma = st.number_input(
            "γ (relative risk aversion)",
            min_value=0.0,
            max_value=10.0,
            value=float((config.get("utilityTransform") or {}).get("gamma", 0.5)),
            step=0.1,
        )
        config["utilityTransform"] = {"type": "CRRA", "gamma": gamma, "offset": 1.0}
    else:
        cols = st.columns(2)
        alpha = cols[0].number_input(
            "α (envy)",
            min_value=0.0,
            max_value=2.0,
            value=float((config.get("utilityTransform") or {}).get("alpha", 0.4)),
            step=0.05,
        )
        beta = cols[1].number_input(
            "β (guilt)",
            min_value=0.0,
            max_value=2.0,
            value=float((config.get("utilityTransform") or {}).get("beta", 0.6)),
            step=0.05,
        )
        config["utilityTransform"] = {"type": "FehrSchmidt", "alpha": alpha, "beta": beta}

    eq_default = ", ".join(config.get("equilibria", []) or [])
    raw_eq = st.text_input(
        "Equilibrium combination keys (comma-separated, e.g. combination4)",
        value=eq_default,
    )
    config["equilibria"] = [s.strip() for s in raw_eq.split(",") if s.strip()]

    pareto = st.number_input(
        "Pareto-optimal sum (used for welfare efficiency)",
        min_value=0.0,
        value=float(config.get("paretoOptimalSum") or 0.0),
        step=1.0,
    )
    if pareto > 0:
        config["paretoOptimalSum"] = pareto
    else:
        config.pop("paretoOptimalSum", None)
    return config


def replay_form(config: Dict[str, Any]) -> Dict[str, Any]:
    cols = st.columns(3)
    seed = cols[0].number_input(
        "Master seed (blank = nondeterministic)",
        min_value=0,
        max_value=10**6,
        value=int(config.get("seed") or 0),
        step=1,
        help="Seeds every internal RNG: types, fake messages, mixed sampling, continuation.",
    )
    seed_count = int(
        cols[1].number_input(
            "Seed count",
            min_value=1,
            max_value=50,
            value=int(config.get("seedCount") or 1),
            step=1,
            help="Number of independent reruns. Aggregated as mean ± 95% CI.",
        )
    )
    cols[2].caption("Seed count > 1 enables CI columns in results.")

    if seed > 0:
        config["seed"] = int(seed)
    else:
        config.pop("seed", None)
    if seed_count > 1:
        config["seedCount"] = seed_count
    else:
        config.pop("seedCount", None)
    return config
