"""Factory: load configs, expand permutations, build and run :class:`FairGame`s.

The factory orchestrates two collaborators:

* :class:`PermutationExpander` — owns the personality / opponent-prior /
  agent / language permutation DataFrame.
* :class:`TournamentBuilder` — generates per-pair configs for round-robin
  tournaments.

This file keeps the high-level orchestration (multi-seed loop,
agent construction, FairGame instantiation) and delegates the
combinatorial work to its collaborators.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

import pandas as pd

from src.agents.agent import Agent, BaselineAgent, LLMAgent
from src.communication.interaction import InteractionGraph
from src.factory import PermutationExpander, TournamentBuilder
from src.game.fairgame import FairGame
from src.io_managers.io_manager import IoManager
from src.utils.logger import get_logger
from src.utils.rng import combine_seed, make_rng

logger = get_logger(__name__)


class FairGameFactory:
    """Loads configuration, expands permutations, constructs and runs games."""

    def __init__(self) -> None:
        self.io_manager = IoManager()
        self.config_all_langs_df = pd.DataFrame()
        self.games: list[FairGame] = []
        self.output_dict: dict[str, Any] = {}
        self._expander = PermutationExpander()
        self._tournament = TournamentBuilder()

    # ----------------------------
    # Permutation generation (delegates)
    # ----------------------------
    def _generate_language_config_df(self, config: dict[str, Any], lang: str) -> pd.DataFrame:
        return self._expander.expand(config, lang)

    # ----------------------------
    # Game creation
    # ----------------------------
    def _create_single_game(
        self,
        config: dict[str, Any],
        game_config_row: dict[str, Any],
        payoff_matrix: dict[str, Any],
        resolved_seed: int | None = None,
        game_index: int = 0,
    ) -> FairGame:
        prompt_template = self.build_prompt_template(config, game_config_row["Language"])
        agents = self.create_agents(game_config_row)

        types_config = self._extract_types_config(config)
        seed = resolved_seed if resolved_seed is not None else config.get("seed")
        # Decorrelate the RNG streams of the games built in one pass: with a
        # single shared seed, RandomChoice baselines, mixed-strategy sampling,
        # fake messages and continuation checks were perfectly correlated
        # across permutation rows, biasing variance over the sweep. Index 0
        # keeps the seed untouched so single-game runs stay byte-identical
        # with historical results; the recorded ``seed`` stays the base seed.
        rng_seed = seed if seed is None or game_index == 0 else combine_seed(seed, game_index)
        rng = make_rng(rng_seed)
        if types_config is not None:
            self._assign_agent_types(agents, types_config, rng=rng)

        from src.game.game_config import GameConfig

        # The nested ``agents.types.commonKnowledge`` spelling must reach the
        # engine's ``types_common_knowledge`` gate; an explicit top-level
        # ``typesAreCommonKnowledge`` still wins.
        if types_config is not None and "typesAreCommonKnowledge" not in config:
            config = {**config, "typesAreCommonKnowledge": types_config["commonKnowledge"]}

        # Input-config shape (keys, defaults, coercions) lives in
        # ``GameConfig.from_raw``; the factory only supplies the per-game
        # collaborators it had to compute first (including the interaction
        # graph, which needs this game's agent roster). The game is fully
        # constructed here — nothing is bolted on afterwards.
        game_cfg = GameConfig.from_raw(
            config,
            language=game_config_row["Language"],
            payoff_matrix_data=payoff_matrix,
            prompt_template=prompt_template,
            types_config=types_config,
            rng=rng,
            seed=seed,
            interaction_graph=InteractionGraph.from_config(config, list(agents.keys())),
        )
        return FairGame.from_config(game_cfg, agents)

    @staticmethod
    def _extract_types_config(config: dict[str, Any]) -> dict[str, Any] | None:
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
        agents: dict[str, Agent],
        types_config: dict[str, Any],
        rng: random.Random,
    ) -> None:
        # ``rng`` is required: an unseeded ``random.Random()`` fallback here
        # was a silent non-determinism trap. Callers thread the run's seeded
        # RNG (seed it with None upstream if nondeterminism is genuinely
        # wanted) so type assignment is reproducible with the rest of the run.
        labels = types_config["labels"]
        probs = types_config["probs"]
        for agent in agents.values():
            agent.agent_type = rng.choices(labels, weights=probs, k=1)[0]

    def create_agents(self, game_config_row: dict[str, Any]) -> dict[str, Agent]:
        from src.agents.baseline_strategies import is_baseline_id, make_baseline  # local import

        agents: dict[str, Agent] = {}
        i = 1
        while f"Agent{i}" in game_config_row:
            name = game_config_row[f"Agent{i}"]
            personality = game_config_row[f"Personality{i}"]
            knowledge = game_config_row[f"OpponentPersonalityProb{i}"]

            llm_col = f"LLM{i}"
            if pd.notna(game_config_row.get(llm_col)):
                llm = game_config_row[llm_col]
            elif "LLM" in game_config_row:
                llm = game_config_row["LLM"]
            else:
                raise ValueError(f"Missing LLM for Agent{i}")

            if is_baseline_id(llm):
                # Keep the user's exact model id as llm_service so the
                # results column shows what the config said (not the
                # canonical strategy name).
                agents[name] = BaselineAgent(
                    name,
                    make_baseline(llm),
                    personality,
                    knowledge,
                    llm_service=llm,
                )
            else:
                agents[name] = LLMAgent(name, llm, personality, knowledge)
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

    def results_games(self) -> dict[str, Any]:
        return self.output_dict

    def all_game_configurations(self) -> pd.DataFrame:
        return self.config_all_langs_df

    def load_config(self, filename: str) -> dict[str, Any]:
        return self.io_manager.load_config(filename)

    def create_games(
        self, config: dict[str, Any], resolved_seed: int | None = None
    ) -> list[FairGame]:
        """Build every game for ``config``.

        ``resolved_seed`` is the seed chosen by the multi-seed sweep for THIS
        pass (an explicit parameter — it is engine-internal state, not a user
        config key). ``None`` falls back to the config's own ``seed``.
        """
        # Reset per-call state: without this a second create_games on the
        # same factory rebuilds ``self.games`` from the union of both calls'
        # configuration rows, silently duplicating games.
        self.config_all_langs_df = pd.DataFrame()
        if self._tournament_enabled(config):
            return self._create_tournament_games(config, resolved_seed)

        for lang in config["languages"]:
            df = self._generate_language_config_df(config, lang)
            self.config_all_langs_df = pd.concat([self.config_all_langs_df, df], ignore_index=True)

        self.games = [
            self._create_single_game(
                config,
                row,
                config["payoffMatrix"],
                resolved_seed=resolved_seed,
                game_index=i,
            )
            for i, (_, row) in enumerate(self.config_all_langs_df.iterrows())
        ]
        return self.games

    # ----------------------------
    # Tournaments
    # ----------------------------
    @staticmethod
    def _tournament_enabled(config: dict[str, Any]) -> bool:
        block = config.get("tournament") or {}
        return bool(block.get("enabled"))

    def _create_tournament_games(
        self, config: dict[str, Any], resolved_seed: int | None = None
    ) -> list[FairGame]:
        """Round-robin: one game per unordered pair of agents.

        Delegates pair generation and per-pair config slicing to
        :class:`TournamentBuilder`; the factory still owns the
        per-language permutation expansion and FairGame instantiation.
        """
        block = config.get("tournament") or {}
        mode = block.get("mode", "round_robin")
        symmetric = bool(block.get("symmetric", True))
        names = list(config["agents"]["names"])
        pairs = self._tournament.pairs(names, mode=mode, symmetric=symmetric)

        base_seed = resolved_seed if resolved_seed is not None else config.get("seed")
        self.games = []
        for pair_idx, pair in enumerate(pairs):
            pair_config, pair_seed = self._tournament.build_pair_config(
                config, pair, pair_idx, resolved_seed=base_seed
            )
            pair_df = pd.DataFrame()
            for lang in pair_config["languages"]:
                lang_df = self._generate_language_config_df(pair_config, lang)
                lang_df["TournamentPair"] = f"{pair[0]}_vs_{pair[1]}"
                pair_df = pd.concat([pair_df, lang_df], ignore_index=True)
            self.config_all_langs_df = pd.concat(
                [self.config_all_langs_df, pair_df], ignore_index=True
            )
            for row_idx, (_, row) in enumerate(pair_df.iterrows()):
                self.games.append(
                    self._create_single_game(
                        pair_config,
                        row,
                        pair_config["payoffMatrix"],
                        resolved_seed=pair_seed,
                        game_index=row_idx,
                    )
                )
        return self.games

    def run_games(
        self,
        progress_cb: Callable[[dict[str, Any]], None] | None = None,
        _base: int = 0,
        _grand_total: int | None = None,
    ) -> None:
        """Run every built game in order.

        When ``progress_cb`` is supplied it is invoked once *after* each game
        finishes with a dict ``{completed, total, name, language}``. ``_base``
        and ``_grand_total`` let a multi-seed caller report a cumulative count
        across several ``run_games`` passes (see ``create_and_run_games``).
        """
        total = _grand_total if _grand_total is not None else len(self.games)
        logger.info("Running %d game(s)", len(self.games))
        for i, game in enumerate(self.games):
            logger.info("Game %d: %s (%s)", i, game.name, game.language)
            history = game.run()
            self._upload_output(game, history, i)
            logger.info("Game %d completed", i)
            if progress_cb is not None:
                progress_cb(
                    {
                        "completed": _base + i + 1,
                        "total": total,
                        "name": game.name,
                        "language": game.language,
                    }
                )

    def load_config_create_and_run_games(self, filename: str) -> dict[str, Any]:
        config = self.load_config(filename)
        return self.create_and_run_games(config)

    def create_and_run_games(
        self,
        config: dict[str, Any],
        progress_cb: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        processed = self.io_manager.process_and_validate_configuration(config)
        seeds = self.resolve_seeds(processed)

        if len(seeds) <= 1:
            seed = seeds[0] if seeds else None
            if seed is not None:
                processed = {**processed, "seed": seed}
            self.create_games(processed, resolved_seed=seed)
            self.run_games(progress_cb=progress_cb)
            return self.output_dict

        # Multi-seed: run the pipeline once per seed and tag every game.
        # The permutation count is seed-independent, so the grand total is
        # known after the first seed builds its games; report a cumulative
        # count across seeds so progress runs 0..100% over the whole sweep.
        merged: dict[str, Any] = {}
        completed = 0
        grand_total: int | None = None
        for seed in seeds:
            child = dict(processed)
            child["seed"] = seed
            child_factory = FairGameFactory()
            child_factory.set_io_manager(self.io_manager)
            child_factory.create_games(child, resolved_seed=seed)
            if grand_total is None:
                grand_total = len(child_factory.games) * len(seeds)
            child_factory.run_games(
                progress_cb=progress_cb, _base=completed, _grand_total=grand_total
            )
            completed += len(child_factory.games)
            for key, value in child_factory.output_dict.items():
                merged[f"seed{seed}_{key}"] = value
        self.output_dict = merged
        return self.output_dict

    @staticmethod
    def resolve_seeds(config: dict[str, Any]) -> list[int | None]:
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

    def build_prompt_template(self, config: dict[str, Any], lang: str) -> str:
        try:
            return config["promptTemplate"][lang]
        except (KeyError, TypeError):
            return self.io_manager.load_template(config["templateFilename"], lang)
