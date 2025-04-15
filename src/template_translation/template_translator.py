import re
import langcodes
from sentence_transformers import SentenceTransformer, util
from src.llm_connectors.llm_factory_connector import execute_prompt


class TemplateTranslator:
    """
    A utility for translating prompt templates using a Large Language Model (LLM),
    while preserving specific formatting and placeholders, and verifying quality 
    via cosine similarity from an off-the-shelf solution.
    """

    def __init__(self, llm, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initializes the translator with the given LLM instance and loads
        the SentenceTransformer model for off-the-shelf cosine similarity.

        Args:
            llm: A Large Language Model connector identifier or instance 
                 compatible with `execute_prompt`.
            model_name: The name of the SentenceTransformer model used to 
                        embed text for similarity. Defaults to
                        a popular sentence-transformers model.
        """
        self.llm = llm
        # Load a pre-trained SentenceTransformer for embedding & cosine similarity
        self.model = SentenceTransformer(model_name)

    def translate(self, prompt_template: str, lang_code: str, cosine_threshold: float = 0.6) -> str:
        """
        Translates a prompt template into the specified language, ensuring
        placeholders and formatting are preserved. Additionally, computes
        the cosine similarity between the original and translated texts and
        raises an error if the similarity is below the provided threshold.

        Args:
            prompt_template: The prompt text to translate.
            lang_code: A BCP 47 language code (e.g., "fr", "es").
            cosine_threshold: The minimum cosine similarity (between 0 and 1)
                              required for the translation to be accepted.

        Returns:
            A translated version of the prompt template.

        Raises:
            ValueError: If placeholders are not preserved or if the computed
                        cosine similarity is below the specified threshold.
        """
        translation_response = self._evaluate(prompt_template, lang_code)
        cleaned_translation = self._extract_translated_text(translation_response)
        self._validate_placeholders(prompt_template, cleaned_translation)

        similarity = self._calculate_cosine_similarity(prompt_template, cleaned_translation)
        if similarity < cosine_threshold:
            raise ValueError(
                f"Cosine similarity below threshold ({similarity:.3f} < {cosine_threshold}). "
                "Translation may not be semantically correct."
            )
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

    def _calculate_cosine_similarity(self, text1: str, text2: str) -> float:
        """
        Computes the cosine similarity between two texts using a SentenceTransformer
        model for embeddings (off-the-shelf solution).

        Args:
            text1: First text string.
            text2: Second text string.

        Returns:
            A float representing the cosine similarity between the texts.
        """
        # Embed the two texts
        embeddings = self.model.encode([text1, text2], convert_to_tensor=True)
        # Compute the cosine similarity with an off-the-shelf method
        similarity = util.cos_sim(embeddings[0], embeddings[1]).item()
        return similarity

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
