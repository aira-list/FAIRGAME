import os
from pathlib import Path

from src.io_managers.file_manager import FileManager
from src.io_managers.configuration_validator import ConfigValidator
from src.utils.utils import get_project_root

# Get the absolute path of the current script
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)

# Get the absolute path of the current script
script_path = Path(__file__).resolve()

project_root = get_project_root(script_path, 3)
DEFAULT_RESOURCES = project_root / "resources"

class IoManager:
    """
    Orchestrates reading config files, validating their structure,
    and loading corresponding template files.
    """

    def __init__(
        self,
        root_path: str = DEFAULT_RESOURCES,
        config_path: str = "config",
        game_path: str = "game_templates",
    ):
        self.file_manager = FileManager()
        self.config_validator = ConfigValidator()

        self.config_path = Path(root_path) / config_path
        self.game_path = Path(root_path) / game_path

    def load_config(self, config_filename: str) -> dict:
        """
        Reads a configuration file (JSON) from disk and returns it without validation.
        """
        config_filepath = self.config_path / config_filename
        return self.file_manager.read_json_file(config_filepath)

    def process_and_validate_configuration(self, config_data: dict) -> dict:
        """
        Validates the configuration structure and content.
        """
        return self.config_validator.validate_config_structure(config_data)

    def load_template(self, filename: str, lang: str) -> str:
        """
        Loads the content of a template file based on a language code.
        """
        template_filepath = self.game_path / f"{filename}_{lang}.txt"
        return self.file_manager.load_text_file(template_filepath)
