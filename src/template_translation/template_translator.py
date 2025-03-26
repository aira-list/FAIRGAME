import re
import langcodes

from src.llm_connectors.llm_factory_connector import execute_prompt

class TemplateTranslator:
    """
    A utility for translating prompt templates using a Large Language Model (LLM),
    while preserving specific formatting and placeholders.
    """

    def __init__(self, llm):
        """
        Initializes the translator with the given LLM instance.

        Args:
            llm: A Large Language Model connector identifier or instance 
                 compatible with `execute_prompt`.
        """
        self.llm = llm

    def translate(self, prompt_template: str, lang_code: str) -> str:
        """
        Translates a prompt template into the specified language, ensuring
        placeholders and formatting are preserved.

        Args:
            prompt_template: The prompt text to translate.
            lang_code: A BCP 47 language code (e.g., "fr", "es").

        Returns:
            A translated version of the prompt template.
        """
        translation_response = self._evaluate(prompt_template, lang_code)
        cleaned_translation = self._extract_translated_text(translation_response)
        self._validate_placeholders(prompt_template, cleaned_translation)
        return cleaned_translation

    def _evaluate(self, prompt_template: str, lang_code: str) -> str:
        """
        Fills the translation prompt template and executes it with the LLM.

        Args:
            prompt_template: The prompt to be translated.
            lang_code: Language code to translate the prompt into.

        Returns:
            Raw response from the LLM.
        """
        language_name = langcodes.get(lang_code).language_name()
        filled_prompt = self._template.format(
            prompt_template=prompt_template,
            language=language_name
        )
        return execute_prompt(self.llm, filled_prompt)

    def _extract_translated_text(self, text: str) -> str:
        """
        Extracts the actual translation from the LLM response using a regex pattern.

        Args:
            text: Raw text returned by the LLM.

        Returns:
            Extracted translation string.
        """
        pattern = r"(translation.*?:|The .*?is:)\s*(.+)"
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        return matches[-1][1].strip() if matches else text

    def _extract_placeholders(self, text: str) -> list:
        """
        Identifies all placeholders in the text.

        Args:
            text: Input text.

        Returns:
            List of placeholder strings found.
        """
        return re.findall(r'\{(.*?)\}', text)

    def _validate_placeholders(self, original: str, translated: str):
        """
        Validates that placeholders from the original text are preserved in the translation.

        Args:
            original: Original text with placeholders.
            translated: Translated text to validate.

        Raises:
            ValueError: If placeholders are not preserved exactly.
        """
        original_ph = self._extract_placeholders(original)
        translated_ph = self._extract_placeholders(translated)
        if original_ph != translated_ph:
            raise ValueError("Translation did not preserve the placeholders.")

    def check_all_placeholders_preserved(self, original_text, second_text):
        """Public method to validate placeholders are preserved (for test compatibility)."""
        self._validate_placeholders(original_text, second_text)

    @property
    def _template(self) -> str:
        """
        The prompt template used for translation, with instructions for the LLM.

        Returns:
            The template string for LLM prompting.
        """
        return (
            "You must provide a translation in {language} of the following sentence:\n\n"
            "\"{prompt_template}\"\n\n"
            "It is CRITICAL to maintain the exact semantic meaning.\n"
            "It is CRITICAL not to translate placeholders in the format {{PLACEHOLDER}}.\n"
            "It is CRITICAL to preserve the indentation, so:\n"
            "1) Insert a newline character when there is a new line.\n"
            "2) Preserve format {{PLACEHOLDER}}: [sentence] when you encounter it.\n"
            "Return ONLY the translation. DO NOT include any additional explanation or text."
        )