import sys
import os
from pathlib import Path
from typing import Dict, Any
import requests
from dotenv import load_dotenv

from src.io_managers.file_manager import FileManager
from src.results_processing.results_processor import ResultsProcessor

RESOURCES_PATH = Path("resources")
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
    return os.getenv("FAIRGAME_URL", "http://127.0.0.1:5003/create_and_run_games")


class GamesRunner:
    """
    Orchestrates the running of games either locally or via API.
    """

    def __init__(self, call_type: str, config: Dict[str, Any], templates: Dict[str, str], fairgame_url: str) -> None:
        """
        Args:
            call_type (str): Type of call ("local" or "api").
            config (Dict[str, Any]): Game configuration dictionary.
            templates (Dict[str, str]): Mapping of language -> template text.
            fairgame_url (str): URL for the FairGame API (if using "api" call_type).
        """
        self.call_type = call_type
        self.config = config
        self.templates = templates
        self.config["promptTemplate"] = self.templates
        self.fairgame_url = fairgame_url

    def run(self) -> Dict[str, Any]:
        """
        Executes the game based on call_type ("local" or "api").
        """
        if self.call_type == "local":
            return self._local_call()
        elif self.call_type == "api":
            return self._api_call()
        else:
            raise ValueError("Invalid call type. Expected 'local' or 'api'.")

    def _local_call(self) -> Dict[str, Any]:
        """
        Execute the game locally using FairGameFactory.
        """
        from src.fairgame_factory import FairGameFactory
        game_factory = FairGameFactory()
        return game_factory.create_and_run_games(self.config)

    def _api_call(self) -> Dict[str, Any]:
        """
        Execute the game by sending a POST request to the FairGame API.
        """
        response = requests.post(self.fairgame_url, json=self.config, headers=HEADERS)
        return response.json()

def parse_call_type(argv: list) -> str:
    """
    Extract the call type ("local" or "api") from command-line arguments.
    """
    if len(argv) < 2:
        raise ValueError("Call type argument ('local' or 'api') is required.")
    return argv[1]

def load_template_file(template_name: str, language: str) -> str:
    """
    Loads a game template file based on template name and language.
    """
    template_filepath = TEMPLATES_PATH / f"{template_name}_{language}.txt"
    return FileManager.read_template_file(template_filepath)

def load_config_file(config_dir: str, config_name: str) -> Dict[str, Any]:
    """
    Loads a JSON config file for the game.
    """
    config_filepath = CONFIG_PATH / config_dir / f"{config_name}.json"
    return FileManager.read_json_file(config_filepath)

def save_results(results: Dict[str, Any], config_name: str) -> None:
    """
    Convert results to a DataFrame and save as CSV.
    """
    results_processor = ResultsProcessor()
    df = results_processor.process(results)
    results_filepath = RESULTS_PATH / f"results_{config_name}.csv"
    FileManager.save_results_csv(df, results_filepath)

def main() -> None:
    """
    Main entry point, showing how to use the FileManager and GamesRunner.
    """
    # 1. Determine the call type
    call_type = parse_call_type(sys.argv)

    # 2. Load environment variables
    fairgame_url = load_env_variables()

    # 3. Define input parameters (adjust as needed)
    config_dir = "prisoner_dilemma"
    config_name = "prisoner_dilemma_round_known_conventional"
    template_name = "prisoner_dilemma"
    language = "en"

    # 4. Load necessary files
    template_content = load_template_file(template_name, language)
    config = load_config_file(config_dir, config_name)

    # 5. Create the runner and run the games
    runner = GamesRunner(call_type, config, {language: template_content}, fairgame_url)
    results = runner.run()

    # 6. Save results
    save_results(results, config_name)

if __name__ == "__main__":
    main()
