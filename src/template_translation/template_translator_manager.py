
import json
import sys
import requests
from pathlib import Path

from src.template_translation.template_translator import TemplateTranslator

class TemplateTranslatorManager:
    """
    A class to translate and save game templates using either a local or an API call.

    Attributes:
        llm (str): The language model identifier.
        call_type (str): The type of call to use for translation ('local' or 'api').
        lang_to (str): The target language code.
        templates_path (Path): The path to the templates directory.
    """

    def __init__(self, llm: str, call_type: str, lang_to: str, templates_path: Path = Path("resources/game_templates")):
        """
        Initializes TemplateTranslatorApp with the given parameters.

        Args:
            llm (str): The language model identifier.
            call_type (str): The type of call to use for translation ('local' or 'api').
            lang_to (str): The target language code.
            templates_path (Path, optional): The path to the templates directory. 
                                             Defaults to Path("resources/game_templates").
        """
        self.llm = llm
        self.call_type = call_type
        self.lang_to = lang_to
        self.templates_path = templates_path

    def translate_template(self, template: str) -> str:
        """
        Translates a template using the specified call type.

        Args:
            template (str): The template content to be translated.

        Returns:
            str: The translated template.
        
        Raises:
            ValueError: If the call type is not 'local' or 'api'.
        """
        if self.call_type == 'local':
            return self._local_call(template)
        elif self.call_type == 'api':
            return self._api_call(template)
        else:
            raise ValueError("Invalid call type specified: must be 'local' or 'api'.")

    def _local_call(self, template: str) -> str:
        """
        Translates the template using a local translation method (LLMTemplateTranslator).

        Args:
            template (str): The template content to be translated.

        Returns:
            str: The translated template.
        """
        translator = TemplateTranslator(self.llm)
        return translator.translate(template, self.lang_to)

    def _api_call(self, template: str) -> str:
        """
        Translates the template using an API call.

        Args:
            template (str): The template content to be translated.

        Returns:
            str: The translated template.
        """
        url = "http://127.0.0.1:5003/translate_template"
        headers = {"Content-Type": "application/json"}
        data = {"llm": self.llm, "template": template, "lang_to": self.lang_to}
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json().get('translation', '')

    def save_translation(self, original_filepath: Path, translation: str) -> Path:
        """
        Saves the translated template to a new file.

        The new filename is derived from the original filename by replacing the 
        language code part with the target language.

        Args:
            original_filepath (Path): The path to the original template file.
            translation (str): The translated template content.

        Returns:
            Path: The path to the saved translated file.
        """
        # Split the filename (without extension) and replace the last part with the target language.
        parts = original_filepath.stem.split('_')
        fixed_part = "_".join(parts[:-1])
        new_filename = f"{fixed_part}_{self.lang_to}.txt"
        translated_filepath = original_filepath.parent / new_filename

        with translated_filepath.open("w", encoding="utf-8") as file:
            file.write(translation)
        return translated_filepath

    def translate_and_save(self, filepath: Path) -> Path:
        """
        Reads a template file, translates its content, and saves the translation.

        Args:
            filepath (Path): The path to the template file to be translated.

        Returns:
            Path: The path to the saved translated file.
        """
        with filepath.open("r", encoding="utf-8") as file:
            template = file.read()
        translation = self.translate_template(template)
        return self.save_translation(filepath, translation)


def main():
    """
    Main function to execute the template translation process.

    Expects command-line arguments:
        1. Target language code (lang_to)
        2. Language model identifier (llm)
        3. Call type ('local' or 'api')
    """
    if len(sys.argv) < 4:
        print("Usage: python template_translator.py <lang_to> <llm> <call_type>")
        sys.exit(1)

    lang_to = sys.argv[1]
    llm = sys.argv[2]
    call_type = sys.argv[3]

    ROOT_DIR = Path("resources/game_templates")
    
    # Example file to demonstrate usage
    example_filepath = ROOT_DIR / "prisoner_dilemma_en.txt"

    app = TemplateTranslatorManager(
        llm=llm,
        call_type=call_type,
        lang_to=lang_to,
        templates_path=ROOT_DIR
    )

    translated_file = app.translate_and_save(example_filepath)
    print(f"Translated template saved to: {translated_file}")

if __name__ == "__main__":
    main()
