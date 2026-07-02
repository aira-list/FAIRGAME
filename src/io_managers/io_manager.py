from pathlib import Path

from src.io_managers.configuration_validator import ConfigValidator
from src.io_managers.file_manager import FileManager
from src.utils.utils import get_resources_dir

# The paper's resources/ folder now lives in the sibling
# Fairgame_paper_evaluations project (see get_resources_dir).
DEFAULT_RESOURCES = get_resources_dir()


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
        """Load a per-language template file.

        Tries ``.txt`` first, then ``.rtf`` (some shipped templates for
        languages with right-to-left or CJK scripts arrived in RTF). The
        RTF reader strips formatting before returning the plain text.
        """
        stem = self.game_path / f"{filename}_{lang}"
        # Containment guard: ``filename``/``lang`` can be attacker-controlled
        # (e.g. an inline config's ``templateFilename`` reaches here via
        # /api/runs). Reject anything that resolves outside game_templates/ so
        # a traversal like "../../etc/passwd" can't read arbitrary files.
        base = self.game_path.resolve()
        resolved_stem = stem.resolve()
        if base != resolved_stem and base not in resolved_stem.parents:
            raise ValueError(f"Invalid template name {filename!r}")
        for suffix in (".txt", ".rtf"):
            candidate = stem.with_suffix(suffix)
            if candidate.is_file():
                return self.file_manager.read_template_file(candidate)
        raise FileNotFoundError(
            f"Template not found: {stem.with_suffix('.txt')} or {stem.with_suffix('.rtf')}"
        )
