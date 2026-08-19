"""FAIRGAME command-line runner.

Runs a single game configuration either in-process ("local") or against a
running FAIRGAME API ("api"), then writes the results CSV::

    python main.py local prisoner_dilemma/prisoner_dilemma_round_known_conventional
    python main.py api  prisoner_dilemma/prisoner_dilemma_round_known_conventional \
        --template prisoner_dilemma --language en --out results/my_run.csv

The config argument is a path under ``<resources>/config/`` (without the
``.json`` suffix); the template defaults to the config's directory name. For
batch experiment sweeps use :mod:`src.factory.experiment` instead — this entry point
is deliberately a one-config runner.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from src.io_managers.file_manager import FileManager
from src.results_processing.results_processor import ResultsProcessor
from src.utils.utils import get_resources_dir

RESOURCES_PATH = get_resources_dir()
TEMPLATES_PATH = RESOURCES_PATH / "game_templates"
CONFIG_PATH = RESOURCES_PATH / "config"
RESULTS_PATH = RESOURCES_PATH / "results"

HEADERS = {"Content-Type": "application/json"}


def load_env_variables() -> str:
    """
    Load environment variables and return the FairGame API URL.
    Defaults to a local URL if FAIRGAME_URL is not set.
    """
    load_dotenv()
    return os.getenv("FAIRGAME_URL", "http://127.0.0.1:4263/api/runs")


class GamesRunner:
    """
    Orchestrates the running of games either locally or via API.
    """

    def __init__(
        self, call_type: str, config: dict[str, Any], templates: dict[str, str], fairgame_url: str
    ) -> None:
        """
        Args:
            call_type (str): Type of call ("local" or "api").
            config (Dict[str, Any]): Game configuration dictionary. Copied —
                the caller's dict is never mutated.
            templates (Dict[str, str]): Mapping of language -> template text.
            fairgame_url (str): URL for the FairGame API (if using "api" call_type).
        """
        self.call_type = call_type
        self.config = dict(config)
        self.templates = templates
        self.config["promptTemplate"] = self.templates
        # ``templateFilename`` is mutually exclusive with ``promptTemplate``
        # in the validator. The CLI provides the template inline, so drop
        # any file-pointer the config might also have set.
        self.config.pop("templateFilename", None)
        self.fairgame_url = fairgame_url

    def run(self) -> dict[str, Any]:
        """
        Executes the game based on call_type ("local" or "api").
        """
        if self.call_type == "local":
            return self._local_call()
        elif self.call_type == "api":
            return self._api_call()
        else:
            raise ValueError("Invalid call type. Expected 'local' or 'api'.")

    def _local_call(self) -> dict[str, Any]:
        """
        Execute the game locally using FairGameFactory.
        """
        from src.factory.fairgame_factory import FairGameFactory

        game_factory = FairGameFactory()
        return game_factory.create_and_run_games(self.config)

    def _api_call(self) -> dict[str, Any]:
        """
        Execute the game by sending a POST request to the FairGame API.

        ``POST /api/runs`` expects the configuration wrapped in a ``config``
        key and returns ``{"id": ..., "rows": [...]}`` where ``rows`` are the
        already-processed result records.
        """
        # Bounded so a hung server fails loudly instead of blocking forever;
        # generous because a run legitimately spans many LLM calls.
        response = requests.post(
            self.fairgame_url, json={"config": self.config}, headers=HEADERS, timeout=3600
        )
        response.raise_for_status()
        return response.json()


def load_template_file(template_name: str, language: str) -> str:
    """
    Loads a game template file based on template name and language.
    """
    template_filepath = TEMPLATES_PATH / f"{template_name}_{language}.txt"
    return FileManager.read_template_file(template_filepath)


def load_config_file(config_ref: str) -> dict[str, Any]:
    """Load ``<resources>/config/<config_ref>.json``."""
    config_filepath = CONFIG_PATH / f"{config_ref}.json"
    return FileManager.read_json_file(config_filepath)


def save_results(results: dict[str, Any], out_path: Path) -> None:
    """
    Convert results to a DataFrame and save as CSV.

    A local run yields raw game outcomes that still need processing; an API
    run already returns processed records under ``rows``.
    """
    if "rows" in results:
        import pandas as pd

        df = pd.DataFrame(results["rows"])
    else:
        df = ResultsProcessor().process(results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    FileManager.save_results_csv(df, out_path)


def parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "call_type",
        choices=("local", "api"),
        help="Run in-process (local) or against a FAIRGAME API (api).",
    )
    parser.add_argument(
        "config",
        help="Config path under <resources>/config/, without .json "
        "(e.g. prisoner_dilemma/prisoner_dilemma_round_known_conventional).",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="Template basename under <resources>/game_templates/ "
        "(default: the config's directory name).",
    )
    parser.add_argument("--language", default="en", help="Template language suffix (default: en).")
    parser.add_argument(
        "--out",
        default=None,
        type=Path,
        help="Output CSV path (default: <resources>/results/results_<config>.csv).",
    )
    return parser.parse_args(argv)


def main(argv: list | None = None) -> None:
    args = parse_args(argv)
    fairgame_url = load_env_variables()

    config_ref = args.config.strip("/")
    template_name = args.template or Path(config_ref).parts[0]
    template_content = load_template_file(template_name, args.language)
    config = load_config_file(config_ref)

    runner = GamesRunner(args.call_type, config, {args.language: template_content}, fairgame_url)
    results = runner.run()

    out = args.out or RESULTS_PATH / f"results_{Path(config_ref).name}.csv"
    save_results(results, out)
    print(f"Results written to {out}")


if __name__ == "__main__":
    sys.exit(main())
