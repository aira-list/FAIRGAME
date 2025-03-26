import json
from pathlib import Path
from striprtf.striprtf import rtf_to_text

class FileManager:
    """
    Handles reading and loading of files (JSON or text/RTF), 
    plus saving output (e.g., CSV).
    """

    @staticmethod
    def read_json_file(filepath: Path) -> dict:
        """
        Reads a JSON file and returns its content as a dictionary.

        Raises:
            FileNotFoundError: If the file is not found.
            ValueError: If the file is not valid JSON.
        """
        try:
            with filepath.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filepath}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON in '{filepath}': {e}")

    @staticmethod
    def load_text_file(filepath: Path) -> str:
        """
        Reads a text file and returns its content as a string.

        Raises:
            FileNotFoundError: If the file is not found.
        """
        try:
            return filepath.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filepath}")

    @staticmethod
    def load_rtf_file(filepath: Path) -> str:
        """
        Reads an RTF file, converts its content to plain text, and returns it.

        Raises:
            FileNotFoundError: If the file is not found.
        """
        try:
            with filepath.open("r", encoding="utf-8") as file:
                return rtf_to_text(file.read())
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filepath}")

    @staticmethod
    def read_template_file(filepath: Path) -> str:
        """
        Reads a template file, which may be .txt or .rtf.
        Uses the appropriate loader based on the file extension.

        Raises:
            FileNotFoundError: If the file is not found.
        """
        if filepath.suffix.lower() == ".rtf":
            return FileManager.load_rtf_file(filepath)
        else:
            return FileManager.load_text_file(filepath)

    @staticmethod
    def save_results_csv(df, filepath: Path) -> None:
        """
        Saves a DataFrame to a CSV file at the specified path.

        Args:
            df (pandas.DataFrame): DataFrame containing the results to save.
            filepath (Path): Path to the output CSV file.
        """
        df.to_csv(filepath, index=False)
