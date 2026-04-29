"""Reusable Streamlit form widgets for editing FAIRGAME configs.

Every widget has a plain-English label with the academic term in
parentheses, plus an informative ``help=`` tooltip explaining *why* the
parameter matters and what reasonable values look like. The intent is for
a non-expert user to make sensible choices without consulting the docs.

The helpers take a config dict by reference and return the (possibly
edited) version. They are stateless so each page can render the same
widget without leaking values across pages.
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


# ---- Basics --------------------------------------------------------------

def basics_form(config: Dict[str, Any]) -> Dict[str, Any]:
    """Edit name, rounds, languages, fake-comm flag."""
    cols = st.columns([2, 1, 1])
    config["name"] = cols[0].text_input(
        "Scenario name",
        value=config.get("name", "Untitled scenario"),
        help=(
            "Used in result filenames and logs. Pick something memorable so "
            "you can find this run later on the Results page."
        ),
    )
    config["nRounds"] = int(
        cols[1].number_input(
            "Number of rounds",
            min_value=1,
            max_value=200,
            value=int(config.get("nRounds", 1)),
            step=1,
            help=(
                "How many rounds each game lasts. Most classical 2×2 games "
                "(Prisoner's Dilemma, Stag Hunt) are studied as one-shot "
                "(1 round); repeated games typically use 5–20 rounds."
            ),
        )
    )
    config["nRoundsIsKnown"] = cols[2].checkbox(
        "Tell agents the round count",
        value=bool(config.get("nRoundsIsKnown", True)),
        help=(
            "If ON, agents are told upfront how many rounds the game will "
            "last. Affects backward-induction reasoning: in a finite "
            "Prisoner's Dilemma, knowing the end-date pushes rational "
            "agents toward defection."
        ),
    )

    languages_default = ", ".join(config.get("languages", ["en"]))
    raw_langs = st.text_input(
        "Languages (comma-separated)",
        value=languages_default,
        help=(
            "BCP-47 codes such as 'en', 'fr', 'ar', 'cn', 'vn'. Each "
            "language must have matching entries under the agents' "
            "personalities and the payoff-matrix strategies. Use multiple "
            "languages to study cross-lingual behavioural differences."
        ),
    )
    config["languages"] = [s.strip() for s in raw_langs.split(",") if s.strip()]

    cols2 = st.columns(2)
    config["agentsCommunicate"] = cols2[0].checkbox(
        "Allow agents to chat each round",
        value=bool(config.get("agentsCommunicate", False)),
        help=(
            "If ON, each agent sends a free-text message to the other(s) "
            "before choosing a strategy. Useful for studying whether "
            "agents can negotiate, signal, or deceive."
        ),
    )
    config["allAgentPermutations"] = cols2[1].checkbox(
        "Run every personality combination",
        value=bool(config.get("allAgentPermutations", True)),
        help=(
            "If ON, the engine runs the game once for every combination of "
            "personalities and opponent priors you list, not just the "
            "matched 1:1 pairing. Symmetric pairs are deduplicated when "
            "all agents share an LLM. Turn it OFF for a single targeted run."
        ),
    )
    return config


# ---- Agents --------------------------------------------------------------

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
        help=(
            "Most classical games are 2-player. Three or more agents "
            "stress-test the permutation engine and let you study "
            "N-player dilemmas like Volunteer's Dilemma."
        ),
    )

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
                "Name",
                value=names[i],
                key=f"agent_name_{i}",
                help="Display name for this agent. Appears in results.",
            ).strip() or f"agent{i + 1}"
            edited_names.append(new_name)
            edited_probs.append(
                float(
                    c2.number_input(
                        "Belief about opponent (%)",
                        min_value=0,
                        max_value=100,
                        value=int(probs[i]),
                        key=f"agent_prob_{i}",
                        help=(
                            "How likely this agent thinks its opponent is "
                            "to *match its declared personality*. 0 means "
                            "the personality is not mentioned in the "
                            "prompt; 100 means the agent is told with full "
                            "confidence."
                        ),
                    )
                )
            )
            current_llm = llms_dict.get(names[i], fallback_llm)
            llm_idx = options.index(current_llm) if current_llm in options else 0
            edited_llms[new_name] = c3.selectbox(
                "Model or strategy",
                options=options,
                index=llm_idx,
                key=f"agent_llm_{i}",
                help=(
                    "Pick an LLM (e.g. OpenAIGPT4o) or a deterministic "
                    "**Baseline** strategy (Tit-for-Tat, Always Cooperate, "
                    "Grim Trigger…). Mixing one LLM agent with one "
                    "baseline is a good way to benchmark."
                ),
            )

            for lang in languages:
                edited_personalities[lang].append(
                    st.text_input(
                        f"Personality ({lang})",
                        value=personalities[lang][i],
                        key=f"agent_pers_{lang}_{i}",
                        help=(
                            "A short adjective ('cooperative', 'selfish', "
                            "'aggressive', 'cautious'). Injected into the "
                            "agent's prompt as 'You are {personality}.'"
                        ),
                    )
                )

    agents["names"] = edited_names
    agents["personalities"] = edited_personalities
    agents["opponentPersonalityProb"] = edited_probs
    config["agents"] = agents

    config["llms"] = edited_llms
    config.pop("llm", None)
    return config


# ---- Theory of Mind -----------------------------------------------------

def tom_form(config: Dict[str, Any]) -> Dict[str, Any]:
    cols = st.columns(2)
    config["elicitBeliefs"] = cols[0].checkbox(
        "Ask agents to predict the opponent (belief elicitation)",
        value=bool(config.get("elicitBeliefs", False)),
        help=(
            "Before each choice, the agent must output a JSON probability "
            "distribution over its opponent's strategies. Enables the "
            "**Brier-score** column in results — lower is better calibration."
        ),
    )
    config["tomOrder"] = int(
        cols[1].select_slider(
            "Theory-of-Mind order",
            options=[0, 1, 2],
            value=int(config.get("tomOrder", 1)),
            help=(
                "How much information about the opponent's mind to put in "
                "the prompt:\n"
                "• 0 — opponent personality is hidden.\n"
                "• 1 — opponent personality + prior shown (default).\n"
                "• 2 — additionally tell the agent its opponent is also "
                "reasoning about it (recursive).\n"
                "Run the same scenario at all three orders to ablate."
            ),
        )
    )

    use_types = st.checkbox(
        "Add a private agent-type system (Bayesian games)",
        value=bool(config.get("agents", {}).get("types")),
        help=(
            "Each agent draws a private 'type' from a prior distribution. "
            "The type label can be inserted into the agent's prompt via "
            "{ownType}. The opponent does *not* see the realised type, "
            "only the prior (if marked common knowledge)."
        ),
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
            help="Short adjectives drawn at game start, e.g. 'trusting, cynical'.",
        )
        labels_list = [s.strip() for s in labels.split(",") if s.strip()]
        probs_str = st.text_input(
            "Prior probabilities (comma-separated)",
            value=", ".join(str(p) for p in types_block.get("probs", [])),
            help=(
                "How likely each type is. Will be re-normalised if they "
                "don't sum to 1. Leave equal for a uniform prior."
            ),
        )
        try:
            probs_list = [float(s.strip()) for s in probs_str.split(",") if s.strip()]
        except ValueError:
            st.warning("Probabilities must be numeric; falling back to uniform.")
            probs_list = [1 / max(1, len(labels_list))] * len(labels_list)
        common_knowledge = st.checkbox(
            "Type prior is common knowledge",
            value=bool(types_block.get("commonKnowledge", False)),
            help=(
                "If ON, both agents are told the *prior distribution* over "
                "the opponent's possible types (without revealing the "
                "actual draw). Required for Bayesian-game analysis."
            ),
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


# ---- Game theory --------------------------------------------------------

def game_theory_form(config: Dict[str, Any]) -> Dict[str, Any]:
    cols = st.columns(2)
    config["mixedStrategies"] = cols[0].checkbox(
        "Mixed strategies (probabilistic actions)",
        value=bool(config.get("mixedStrategies", False)),
        help=(
            "Instead of picking a single action, the agent emits a "
            "probability distribution over strategies and the engine "
            "samples one. Required to study mixed-strategy equilibria "
            "(e.g. zero-sum games)."
        ),
    )
    config["discountFactor"] = float(
        cols[1].slider(
            "Discount factor (δ) — how much future rounds matter",
            min_value=0.10,
            max_value=1.00,
            value=float(config.get("discountFactor", 1.0)),
            step=0.05,
            help=(
                "Round t's payoff is multiplied by δ^(t-1). 1.0 means no "
                "discounting (all rounds equally important); 0.9 means "
                "round 2 is worth 90% as much as round 1, etc. The "
                "standard model for repeated games."
            ),
        )
    )
    use_continuation = st.checkbox(
        "Stochastic horizon (game can end early)",
        value=config.get("continuationProbability") is not None,
        help=(
            "If ON, after each round there's a fixed probability the game "
            "continues — otherwise it ends. Models indefinite-horizon "
            "interactions where players don't know exactly when the "
            "relationship ends."
        ),
    )
    if use_continuation:
        config["continuationProbability"] = float(
            st.slider(
                "Probability the game continues each round",
                min_value=0.05,
                max_value=1.00,
                value=float(config.get("continuationProbability") or 0.95),
                step=0.05,
                help=(
                    "Higher values mean longer expected games. 0.95 ⇒ "
                    "expected length ~20 rounds."
                ),
            )
        )
    else:
        config.pop("continuationProbability", None)

    transform = st.selectbox(
        "Utility function (how points become satisfaction)",
        options=["identity", "CRRA", "FehrSchmidt"],
        index=["identity", "CRRA", "FehrSchmidt"].index(
            (config.get("utilityTransform") or {}).get("type", "identity")
        ),
        help=(
            "• **identity** — raw payoffs are used directly (default).\n"
            "• **CRRA** — agent is risk-averse: prefers a sure 4 to a "
            "50/50 bet between 0 and 8.\n"
            "• **Fehr-Schmidt** — agent is inequity-averse: dislikes "
            "outcomes where it earns much more or much less than its "
            "opponent."
        ),
    )
    if transform == "identity":
        config.pop("utilityTransform", None)
    elif transform == "CRRA":
        gamma = st.number_input(
            "Risk-aversion (γ) — higher = more risk-averse",
            min_value=0.0,
            max_value=10.0,
            value=float((config.get("utilityTransform") or {}).get("gamma", 0.5)),
            step=0.1,
            help=(
                "γ=0 is risk-neutral; γ=1 is the log-utility case; γ>1 is "
                "very risk-averse. Empirical estimates of human γ "
                "typically fall in [0.5, 2]."
            ),
        )
        config["utilityTransform"] = {"type": "CRRA", "gamma": gamma, "offset": 1.0}
    else:
        cols = st.columns(2)
        alpha = cols[0].number_input(
            "Envy weight (α)",
            min_value=0.0,
            max_value=2.0,
            value=float((config.get("utilityTransform") or {}).get("alpha", 0.4)),
            step=0.05,
            help=(
                "How much the agent suffers when the opponent earns more "
                "than it does. Empirically α ≈ 0.4 in lab studies."
            ),
        )
        beta = cols[1].number_input(
            "Guilt weight (β)",
            min_value=0.0,
            max_value=2.0,
            value=float((config.get("utilityTransform") or {}).get("beta", 0.6)),
            step=0.05,
            help=(
                "How much the agent suffers when *it* earns more than the "
                "opponent. Conventionally β ≤ α."
            ),
        )
        config["utilityTransform"] = {"type": "FehrSchmidt", "alpha": alpha, "beta": beta}

    eq_default = ", ".join(config.get("equilibria", []) or [])
    raw_eq = st.text_input(
        "Equilibrium combinations (advanced)",
        value=eq_default,
        help=(
            "Comma-separated combination keys (e.g. 'combination4') that "
            "you've identified as Nash equilibria. The analysis layer will "
            "report how often play landed on one of them. Leave blank if "
            "you don't want this metric."
        ),
    )
    config["equilibria"] = [s.strip() for s in raw_eq.split(",") if s.strip()]

    pareto = st.number_input(
        "Pareto-optimal joint payoff (advanced)",
        min_value=0.0,
        value=float(config.get("paretoOptimalSum") or 0.0),
        step=1.0,
        help=(
            "The maximum total payoff the players could earn under any "
            "joint strategy. When set, the results gain a "
            "'welfare_efficiency' column = mean(actual sum) / this value. "
            "Leave at 0 to skip."
        ),
    )
    if pareto > 0:
        config["paretoOptimalSum"] = pareto
    else:
        config.pop("paretoOptimalSum", None)
    return config


# ---- Reproducibility ----------------------------------------------------

def replay_form(config: Dict[str, Any]) -> Dict[str, Any]:
    cols = st.columns(3)
    seed = cols[0].number_input(
        "Master seed (0 = nondeterministic)",
        min_value=0,
        max_value=10**6,
        value=int(config.get("seed") or 0),
        step=1,
        help=(
            "Seeds every internal random source: type draws, "
            "fake-message generation, mixed-strategy sampling, "
            "stochastic-horizon termination. Same seed → same run. Use 0 "
            "to leave each run nondeterministic."
        ),
    )
    seed_count = int(
        cols[1].number_input(
            "Number of repetitions (seed count)",
            min_value=1,
            max_value=50,
            value=int(config.get("seedCount") or 1),
            step=1,
            help=(
                "Re-run the entire experiment this many times with "
                "different seeds. Required for confidence intervals; 5–20 "
                "is typical for paper-grade results."
            ),
        )
    )
    cols[2].caption(
        "Set seed count > 1 to get **mean ± 95% CI** columns in the results."
    )

    if seed > 0:
        config["seed"] = int(seed)
    else:
        config.pop("seed", None)
    if seed_count > 1:
        config["seedCount"] = seed_count
    else:
        config.pop("seedCount", None)
    return config
