import unittest
from pathlib import Path

from src.io_managers.io_manager import IoManager
from src.template_translation.template_translator import TemplateTranslator

LLM = 'OpenAIGPT4o'
CONFIG_PATH = Path('unit_tests/game_templates')
BODY_FILEPATH = CONFIG_PATH / 'prisoner_dilemma_en.txt'


class TestTranslation(unittest.TestCase):
    """
    Unit tests for verifying the functionality of the PromptTemplateTranslator.
    
    This suite tests both translation accuracy (e.g., from English to French) and 
    the preservation of placeholder tokens between the original and translated text.
    """

    def setUp(self) -> None:
        # Initialize the IO manager and prompt translator.
        self.io_manager = IoManager()
        self.prompt_translator = TemplateTranslator(LLM)

    def _load_template(self, filepath: Path) -> str:
        """
        Load the template file from the given path.

        Args:
            filepath (Path): Path to the template file.
        
        Returns:
            str: Content of the template file.
        """
        with filepath.open('r', encoding='utf-8') as file:
            return file.read()

    def test_translation_from_en_to_fr(self) -> None:
        """
        Verify that an English prompt template is correctly translated to French.
        
        The output is printed to allow manual verification of translation quality.
        In a more complete test suite, this output might be compared to a reference translation.
        """
        body_template = self._load_template(BODY_FILEPATH)
        fr_translation = self.prompt_translator.translate(body_template, 'fr', cosine_threshold=0.6)
        print(fr_translation)
        # Additional assertions could be added here, e.g., self.assertIsInstance(fr_translation, str)

    def test_all_placeholders_preserved(self) -> None:
        """
        Ensure that placeholder tokens (e.g., '{x}', '{y}') are preserved between the
        base text and its translation.
        
        The translator should raise a ValueError if any placeholder is missing, 
        altered, or mismatched in order or count.
        """
        base_text = 'this is the base text with {x} placeholders and {y} characters and {y} words'
        bugged_text_1 = 'this is a bugged text with {y} placeholders and {y} characters and {x} words'
        bugged_text_2 = 'this is a bugged text with {x} placeholders and {y} characters'
        bugged_text_3 = 'this is a bugged text with {x} placeholders and {y} characters and {z} words'
        correct_text = 'this is a good text with {x} placeholders and {y} characters and {y} words'

        # Expect ValueError when the placeholder ordering or count is inconsistent.
        with self.assertRaises(ValueError):
            self.prompt_translator.check_all_placeholders_preserved(base_text, bugged_text_1)
        with self.assertRaises(ValueError):
            self.prompt_translator.check_all_placeholders_preserved(base_text, bugged_text_2)
        with self.assertRaises(ValueError):
            self.prompt_translator.check_all_placeholders_preserved(base_text, bugged_text_3)
        
        # Verify that the correct translation with preserved placeholders passes.
        self.prompt_translator.check_all_placeholders_preserved(base_text, correct_text)

    def test_cosine_similarity_failure(self) -> None:
        """
        Forces a ValueError by setting a very high cosine similarity threshold
        so the translation will not meet it.
        """
        original_text = "Hello, world!"
        # Attempting translation to French (or any language). 
        # We set the threshold to 1.0 (perfect similarity) which is
        # practically impossible for a translated text to meet.
        with self.assertRaises(ValueError):
            self.prompt_translator.translate(original_text, 'fr', cosine_threshold=1.0)


if __name__ == '__main__':
    unittest.main()
