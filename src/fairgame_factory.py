"""Factory: load configs, expand permutations, build and run :class:`FairGame`s."""

from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from src.agent import Agent
from src.fairgame import FairGame
from src.io_managers.io_manager import IoManager
from src.utils.logger import get_logger
from src.utils.rng import make_rng

logger = get_logger(__name__)


class FakeCommunicationConfig:
    """Configuration holder for the optional fake-communication phase."""

    def __init__(
        self,
        enabled: bool = False,
        message_count: int = 1,
        base: str = "dec",
    ) -> None:
        self.enabled = enabled
        self.message_count = message_count
        self.base = base

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "FakeCommunicationConfig":
        enabled = bool(config.get("fakeCommunication", False))
        if not enabled:
            return cls(enabled=False)
        return cls(
            enabled=True,
            message_count=int(config.get("fakeMessageCount", 1)),
            base=config.get("fakeMessageBase", "dec"),
        )


class FairGameFactory:
    """Loads configuration, expands permutations, constructs and runs games."""

    def __init__(self) -> None:
        self.io_manager = IoManager()
        self.config_all_langs_df = pd.DataFrame()
        self.games: List[FairGame] = []
        self.output_dict: Dict[str, Any] = {}

    # ----------------------------
    # LLM resolution helpers
    # ----------------------------
    def _resolve_llms_for_agents(
        self, full_config: Any, agents: Sequence[str]
    ) -> List[str]:
        n_agents = len(agents)
        # Accept a bare LLM identifier for callers that still pass the legacy
        # third-arg shape (e.g. older test fixtures).
        if isinstance(full_config, str):
            return [full_config] * n_agents
        llms = full_config.get("llms")

        if isinstance(llms, dict):
            return [llms[name] for name in agents]

        if isinstance(llms, (list, tuple)):
            llms_list = list(llms)
            if len(llms_list) != n_agents:
                raise ValueError(
                    f"config['llms'] length ({len(llms_list)}) "
                    f"must equal number of agents ({n_agents})."
                )
            return llms_list

        single = full_config.get("llm")
        if isinstance(single, str):
            return [single] * n_agents

        raise ValueError(
            "Missing LLM configuration: provide 'llm', 'llms' list, or 'llms' dict."
        )

    def _uses_same_llm_for_all_agents(
        self, full_config: Dict[str, Any], agent_names: Sequence[str]
    ) -> bool:
        try:
            llms = self._resolve_llms_for_agents(full_config, agent_names)
        except Exception:
            return False
        return len(set(llms)) == 1

    def _attach_llm_columns(
        self, df: pd.DataFrame, full_config: Dict[str, Any]
    ) -> pd.DataFrame:
        if df.empty:
            return df

        agent_cols = sorted(
            (c for c in df.columns if c.startswith("Agent")),
            key=lambda x: int(x.replace("Agent", "")),
        )
        llm_cols = [f"LLM{i}" for i in range(1, len(agent_cols) + 1)]
        for col in llm_cols:
            if col not in df.columns:
                df[col] = None

        for idx, row in df.iterrows():
            agents = [row[c] for c in agent_cols]
            llms = self._resolve_llms_for_agents(full_config, agents)
            for i, llm in enumerate(llms, start=1):
                df.at[idx, f"LLM{i}"] = llm

        return df

    # ----------------------------
    # Permutation generation
    # ----------------------------
    def _generate_language_config_df(
        self, config: Dict[str, Any], lang: str
    ) -> pd.DataFrame:
        if config["allAgentPermutations"]:
            return self.compute_all_game_configurations(lang, config["agents"], config)
        return self.compute_configuration(lang, config["agents"], config)

    def _compute_agent_configurations(
        self, lang: str, config_agents: Dict[str, Any], full_config: Dict[str, Any]
    ):
        n_agents = len(config_agents["names"])
        agent_combinations = [config_agents["names"]]

        use_combinations = self._uses_same_llm_for_all_agents(
            full_config, config_agents["names"]
        )
        permute = itertools.combinations_with_replacement if use_combinations else itertools.product
        if use_combinations:
            personality_permutations = list(
                permute(config_agents["personalities"][lang], n_agents)
            )
            knowledge_permutations = list(
                permute(config_agents["opponentPersonalityProb"], n_agents)
            )
        else:
            personality_permutations = list(
                permute(config_agents["personalities"][lang], repeat=n_agents)
            )
            knowledge_permutations = list(
                permute(config_agents["opponentPersonalityProb"], repeat=n_agents)
            )

        return agent_combinations, personality_permutations, knowledge_permutations

    def _generate_full_permutations(
        self, agent_combinations, personality_permutations, knowledge_permutations
    ) -> pd.DataFrame:
        rows = []
        for agents in agent_combinations:
            n_agents = len(agents)
            for pers_tuple, know_tuple in itertools.product(
                personality_permutations, knowledge_permutations
            ):
                rows.append(
                    {
                        **{f"Agent{i+1}": agents[i] for i in range(n_agents)},
                        **{f"Personality{i+1}": pers_tuple[i] for i in range(n_agents)},
                        **{
                            f"OpponentPersonalityProb{i+1}": know_tuple[i]
                            for i in range(n_agents)
                        },
                    }
                )
        return pd.DataFrame(rows)

    def compute_all_game_configurations(
        self, lang: str, config_agents: Dict[str, Any], full_config: Dict[str, Any]
    ) -> pd.DataFrame:
        agent_combinations, pers_perms, knowledge_perms = self._compute_agent_configurations(
            lang, config_agents, full_config
        )
        df = self._generate_full_permutations(agent_combinations, pers_perms, knowledge_perms)
        df["Language"] = lang
        return self._attach_llm_columns(df, full_config)

    def compute_configuration(
        self, lang: str, config_agents: Dict[str, Any], full_config: Dict[str, Any]
    ) -> pd.DataFrame:
        n_agents = len(config_agents["names"])
        row = {
            **{f"Agent{i+1}": config_agents["names"][i] for i in range(n_agents)},
            **{
                f"Personality{i+1}": config_agents["personalities"][lang][i]
                for i in range(n_agents)
            },
            **{
                f"OpponentPersonalityProb{i+1}": config_agents["opponentPersonalityProb"][i]
                for i in range(n_agents)
            },
            "Language": lang,
        }
        df = pd.DataFrame([row])
        return self._attach_llm_columns(df, full_config)

    # ----------------------------
    # Game creation
    # ----------------------------
    def _create_single_game(
        self,
        config: Dict[str, Any],
        game_config_row: Dict[str, Any],
        payoff_matrix: Dict[str, Any],
    ) -> FairGame:
        prompt_template = self.build_prompt_template(config, game_config_row["Language"])
        agents = self.create_agents(game_config_row)

        types_config = self._extract_types_config(config)
        seed = config.get("_resolved_seed", config.get("seed"))
        rng = make_rng(seed)
        if types_config is not None:
            self._assign_agent_types(agents, types_config, rng=rng)

        from src.utility import build_utility_transform  # local import to avoid cycles

        game = FairGame(
            config["name"],
            game_config_row["Language"],
            agents,
            config["nRounds"],
            config["nRoundsIsKnown"],
            payoff_matrix,
            prompt_template,
            config["stopGameWhen"],
            config["agentsCommunicate"],
            elicit_beliefs=bool(config.get("elicitBeliefs", False)),
            tom_order=int(config.get("tomOrder", 1)),
            types_config=types_config,
            types_common_knowledge=bool(config.get("typesAreCommonKnowledge", False)),
            utility_transform=build_utility_transform(config.get("utilityTransform")),
            discount_factor=float(config.get("discountFactor", 1.0)),
            continuation_probability=config.get("continuationProbability"),
            equilibria=list(config.get("equilibria", []) or []),
            pareto_optimal_sum=config.get("paretoOptimalSum"),
            mixed_strategies=bool(config.get("mixedStrategies", False)),
            reputation_window=config.get("reputationWindow"),
            reputation_applies=bool(config.get("reputationApplies", True)),
            rng=rng,
            seed=seed,
        )
        game.fake_communication_config = FakeCommunicationConfig.from_config(config)
        # Surface baseline semantics on the game so non-LLM strategies know
        # which key counts as "cooperate" vs "defect".
        baseline_semantics = config.get("baselineSemantics")
        if baseline_semantics:
            game.baseline_semantics = dict(baseline_semantics)
        return game

    @staticmethod
    def _extract_types_config(config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        agents_block = config.get("agents") or {}
        types = agents_block.get("types") if isinstance(agents_block, dict) else None
        if not types:
            return None
        labels = list(types.get("labels", []))
        probs = types.get("probs")
        if probs is None:
            probs = [1.0 / len(labels)] * len(labels)
        return {
            "labels": labels,
            "probs": list(probs),
            "commonKnowledge": bool(types.get("commonKnowledge", False)),
        }

    @staticmethod
    def _assign_agent_types(
        agents: Dict[str, Agent],
        types_config: Dict[str, Any],
        rng: Optional[random.Random] = None,
    ) -> None:
        labels = types_config["labels"]
        probs = types_config["probs"]
        rng = rng or random.Random()
        for agent in agents.values():
            agent.agent_type = rng.choices(labels, weights=probs, k=1)[0]

    def create_agents(self, game_config_row: Dict[str, Any]) -> Dict[str, Agent]:
        from src.baseline_strategies import is_baseline_id, make_baseline  # local import

        agents: Dict[str, Agent] = {}
        i = 1
        while f"Agent{i}" in game_config_row:
            name = game_config_row[f"Agent{i}"]
            personality = game_config_row[f"Personality{i}"]
            knowledge = game_config_row[f"OpponentPersonalityProb{i}"]

            llm_col = f"LLM{i}"
            if pd.notna(game_config_row.get(llm_col, None)):
                llm = game_config_row[llm_col]
            elif "LLM" in game_config_row:
                llm = game_config_row["LLM"]
            else:
                raise ValueError(f"Missing LLM for Agent{i}")

            baseline = make_baseline(llm) if is_baseline_id(llm) else None
            agents[name] = Agent(
                name, llm, personality, knowledge, baseline_strategy=baseline
            )
            i += 1

        return agents

    # ----------------------------
    # IO and orchestration
    # ----------------------------
    def _upload_output(self, game: FairGame, game_history, game_n: int) -> None:
        description = game.description
        # Keep just enough metadata for downstream equilibrium / welfare /
        # regret analysis. We retain the full four-block matrix because
        # regret needs the weight-key matrix too; for a 2x2 game it's tiny.
        full_matrix = description.pop("payoff_matrix", None)
        if full_matrix:
            description["payoff_matrix_summary"] = {
                "weights": full_matrix.get("weights"),
                "strategies": full_matrix.get("strategies"),
                "combinations": full_matrix.get("combinations"),
                "matrix": full_matrix.get("matrix"),
            }
        self.output_dict[f"game_{game_n}"] = {
            "description": description,
            "history": game_history.describe(),
        }

    def set_io_manager(self, manager: IoManager) -> None:
        self.io_manager = manager

    def results_games(self) -> Dict[str, Any]:
        return self.output_dict

    def all_game_configurations(self) -> pd.DataFrame:
        return self.config_all_langs_df

    def load_config(self, filename: str) -> Dict[str, Any]:
        return self.io_manager.load_config(filename)

    def create_games(self, config: Dict[str, Any]) -> List[FairGame]:
        if self._tournament_enabled(config):
            return self._create_tournament_games(config)

        for lang in config["languages"]:
            df = self._generate_language_config_df(config, lang)
            self.config_all_langs_df = pd.concat(
                [self.config_all_langs_df, df], ignore_index=True
            )

        self.games = [
            self._create_single_game(config, row, config["payoffMatrix"])
            for _, row in self.config_all_langs_df.iterrows()
        ]
        return self.games

    # ----------------------------
    # Tournaments
    # ----------------------------
    @staticmethod
    def _tournament_enabled(config: Dict[str, Any]) -> bool:
        block = config.get("tournament") or {}
        return bool(block.get("enabled"))

    def _create_tournament_games(self, config: Dict[str, Any]) -> List[FairGame]:
        """Round-robin: one game per unordered pair of agents.

        Each pair-game inherits the full top-level config but rewrites
        ``agents.names``, ``agents.personalities[lang]`` and any ``llms``
        list/dict to a 2-element slice for the chosen pair. Other config
        axes (languages, permutations, etc.) still apply within each pair.
        """
        block = config.get("tournament") or {}
        mode = block.get("mode", "round_robin")
        if mode != "round_robin":
            raise ValueError(f"Unsupported tournament mode {mode!r}.")
        symmetric = bool(block.get("symmetric", True))

        names = list(config["agents"]["names"])
        if len(names) < 2:
            raise ValueError("Tournament needs at least 2 agents.")

        pairs: List[tuple[str, str]] = []
        for i, ai in enumerate(names):
            for j, aj in enumerate(names):
                if ai == aj:
                    continue
                if symmetric and j <= i:
                    continue
                pairs.append((ai, aj))

        # Build each pair's config once and pair df-rows with their config
        # so we can't lose track of which pair a row belongs to even if
        # subsequent code reorders rows.
        self.games = []
        for pair_idx, pair in enumerate(pairs):
            pair_config = self._build_pair_config(config, pair, pair_idx)
            pair_df = pd.DataFrame()
            for lang in pair_config["languages"]:
                lang_df = self._generate_language_config_df(pair_config, lang)
                lang_df["TournamentPair"] = f"{pair[0]}_vs_{pair[1]}"
                pair_df = pd.concat([pair_df, lang_df], ignore_index=True)
            self.config_all_langs_df = pd.concat(
                [self.config_all_langs_df, pair_df], ignore_index=True
            )
            for _, row in pair_df.iterrows():
                self.games.append(
                    self._create_single_game(pair_config, row, pair_config["payoffMatrix"])
                )
        return self.games

    @staticmethod
    def _build_pair_config(config: Dict[str, Any], pair: tuple[str, str], pair_idx: int) -> Dict[str, Any]:
        """Materialise a per-pair config: only the two agents in ``pair``."""
        pair_config = dict(config)
        # Mark this run with a unique seed branch so multi-seed runs stay
        # deterministic per pair when a master seed is set.
        if pair_config.get("_resolved_seed") is not None:
            pair_config["_resolved_seed"] = int(pair_config["_resolved_seed"]) + pair_idx

        agents_block = dict(config["agents"])
        names = list(config["agents"]["names"])
        idx = [names.index(p) for p in pair]

        agents_block["names"] = list(pair)
        agents_block["personalities"] = {
            lang: [plist[i] for i in idx]
            for lang, plist in config["agents"]["personalities"].items()
        }
        if config["agents"].get("opponentPersonalityProb"):
            opp = config["agents"]["opponentPersonalityProb"]
            agents_block["opponentPersonalityProb"] = (
                [opp[i] for i in idx]
                if len(opp) == len(names)
                else opp  # shared pool, leave as-is
            )
        pair_config["agents"] = agents_block

        # Slice per-agent llm assignments if needed.
        if isinstance(config.get("llms"), dict):
            pair_config["llms"] = {p: config["llms"][p] for p in pair}
        elif isinstance(config.get("llms"), list):
            pair_config["llms"] = [config["llms"][i] for i in idx]

        return pair_config

    def games_info(self) -> List[Dict[str, Any]]:
        return [game.description for game in self.games]

    def run_games(self) -> None:
        logger.info("Running %d game(s)", len(self.games))
        for i, game in enumerate(self.games):
            logger.info("Game %d: %s (%s)", i, game.name, game.language)
            history = game.run()
            self._upload_output(game, history, i)
            logger.info("Game %d completed", i)

    def load_config_create_and_run_games(self, filename: str) -> Dict[str, Any]:
        config = self.load_config(filename)
        return self.create_and_run_games(config)

    def create_and_run_games(self, config: Dict[str, Any]) -> Dict[str, Any]:
        processed = self.io_manager.process_and_validate_configuration(config)
        seeds = self._resolve_seeds(processed)

        if len(seeds) <= 1:
            seed = seeds[0] if seeds else None
            if seed is not None:
                processed = {**processed, "_resolved_seed": seed, "seed": seed}
            self.create_games(processed)
            self.run_games()
            return self.output_dict

        # Multi-seed: run the pipeline once per seed and tag every game.
        merged: Dict[str, Any] = {}
        for seed in seeds:
            child = dict(processed)
            child["_resolved_seed"] = seed
            child["seed"] = seed
            child_factory = FairGameFactory()
            child_factory.set_io_manager(self.io_manager)
            child_factory.create_games(child)
            child_factory.run_games()
            for key, value in child_factory.output_dict.items():
                merged[f"seed{seed}_{key}"] = value
        self.output_dict = merged
        return self.output_dict

    @staticmethod
    def _resolve_seeds(config: Dict[str, Any]) -> List[Optional[int]]:
        """Decide the list of seeds to run, in priority: ``seeds`` > ``seedCount`` > ``seed``."""
        explicit = config.get("seeds")
        if explicit:
            return list(explicit)
        n = config.get("seedCount")
        if isinstance(n, int) and n > 1:
            base = config.get("seed")
            if base is None:
                return list(range(n))
            return [int(base) + i for i in range(n)]
        if "seed" in config and config["seed"] is not None:
            return [int(config["seed"])]
        return [None]

    def build_prompt_template(self, config: Dict[str, Any], lang: str) -> str:
        try:
            return config["promptTemplate"][lang]
        except (KeyError, TypeError):
            return self.io_manager.load_template(config["templateFilename"], lang)
