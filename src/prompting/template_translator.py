import re
from collections import Counter

import langcodes

from src.llm_connectors import execute_prompt

# FAIRGAME deliberately uses "cn" (Chinese) and "vn" (Vietnamese) as language
# codes, but they aren't BCP 47 — langcodes resolves them to "Unknown language
# [cn]", which would end up verbatim in the translation prompt. Map them to
# their ISO 639-1 equivalents before resolution; every other code keeps
# langcodes' behaviour.
_LANG_CODE_ALIASES = {"cn": "zh", "vn": "vi"}


def _language_name(lang_code: str) -> str:
    """Human-readable language name for ``lang_code``, alias-aware."""
    resolved = _LANG_CODE_ALIASES.get(lang_code, lang_code)
    return langcodes.get(resolved).language_name()


class TemplateTranslator:
    """
    Translates prompt templates with a Large Language Model (LLM), preserving
    formatting and placeholders.

    Translation quality is the responsibility of the chosen LLM: FAIRGAME no
    longer runs an embedding-based cosine-similarity gate (that pulled in
    ``sentence-transformers``/torch). The only structural guarantee enforced
    here is that every ``{PLACEHOLDER}`` in the source survives in the output.
    """

    def __init__(self, llm):
        """
        Args:
            llm: A LiteLLM-resolvable model name (or connector identifier)
                 compatible with :func:`src.llm_connectors.execute_prompt`.
                 This is the LLM that performs the translation.
        """
        self.llm = llm

    def translate(
        self, prompt_template: str, lang_code: str, source_lang_code: str | None = None
    ) -> str:
        """
        Translates a prompt template into the specified language, ensuring
        placeholders and formatting are preserved.

        Args:
            prompt_template: The prompt text to translate.
            lang_code: A BCP 47 language code (e.g., "fr", "es").
            source_lang_code: Optional BCP 47 code of the *source* text. Naming
                the source language in the prompt matters when it is not
                English (e.g. a French template translated to Italian).

        Returns:
            A translated version of the prompt template.

        Raises:
            ValueError: If the translation does not preserve the placeholders,
                or the model returned the source text unchanged (echo).
        """
        translation_response = self._evaluate(prompt_template, lang_code, source_lang_code)
        cleaned_translation = self._extract_translated_text(translation_response)
        if self._is_echo(prompt_template, cleaned_translation):
            # Models occasionally echo the quoted source verbatim instead of
            # translating. Retry once with an explicit reminder; give up
            # loudly rather than silently storing an untranslated copy.
            translation_response = self._evaluate(
                prompt_template, lang_code, source_lang_code, retry=True
            )
            cleaned_translation = self._extract_translated_text(translation_response)
            if self._is_echo(prompt_template, cleaned_translation):
                target = _language_name(lang_code)
                raise ValueError(
                    f"The model returned the source text unchanged instead of "
                    f"translating it into {target}. Try again or pick another model."
                )
        self._validate_placeholders(prompt_template, cleaned_translation)
        return cleaned_translation

    def _evaluate(
        self,
        prompt_template: str,
        lang_code: str,
        source_lang_code: str | None = None,
        retry: bool = False,
    ) -> str:
        """
        Fills the translation prompt template and executes it with the LLM.

        Args:
            prompt_template: The prompt to be translated.
            lang_code: Language code to translate the prompt into.
            source_lang_code: Optional language code of the source text.
            retry: True on the second attempt after an echoed response — adds
                an explicit "do not return the text unchanged" reminder.

        Returns:
            Raw response from the LLM.
        """
        language_name = _language_name(lang_code)
        filled_prompt = self._template.format(
            prompt_template=prompt_template, language=language_name
        )
        if source_lang_code:
            source_name = _language_name(source_lang_code)
            filled_prompt += f"\nThe text above is written in {source_name}."
        if retry:
            filled_prompt += (
                f"\nIMPORTANT: your previous answer returned the text unchanged. "
                f"You MUST rewrite it in {language_name}."
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
        out = matches[-1][1].strip() if matches else text.strip()
        return self._strip_wrapping_quotes(out)

    @staticmethod
    def _strip_wrapping_quotes(text: str) -> str:
        """Remove one pair of quotes wrapping the whole answer.

        The translation prompt quotes the source text, so models often quote
        their answer in kind ("…" or “…”); those quotes are not part of the
        template. Only strips when the pair forms ONE span: a text that merely
        *starts and ends* with distinct quoted tokens ('"OptionA" … "OptionB"')
        must not lose its outer characters.
        """
        pairs = {('"', '"'), ("“", "”"), ("'", "'")}
        t = text.strip()
        if len(t) >= 2 and (t[0], t[-1]) in pairs and t[0] not in t[1:-1] and t[-1] not in t[1:-1]:
            return t[1:-1].strip()
        return t

    @staticmethod
    def _is_echo(original: str, translated: str) -> bool:
        """True when the 'translation' is just the source text unchanged.

        Placeholder-dominated templates are exempt: when almost nothing but
        ``{placeholders}`` and punctuation remains, the correct translation
        often IS the source text, and rejecting it would make such templates
        untranslatable.
        """

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip().casefold()

        if norm(original) != norm(translated):
            return False
        # Fewer than three translatable words outside placeholders → an
        # identical output is legitimate, not an echo failure.
        prose = re.sub(r"\{[^{}]*\}", " ", original)
        words = re.findall(r"[^\W\d_]{2,}", prose)
        return len(words) >= 3

    def _extract_placeholders(self, text: str) -> list:
        """
        Identifies all placeholders in the text.

        Args:
            text: Input text.

        Returns:
            List of placeholder strings found.
        """
        return re.findall(r"\{(.*?)\}", text)

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
        # Compare as multisets, not ordered lists: a faithful translation may
        # legitimately reorder ``{a} ... {b}`` (word order differs by
        # language). Only the set-with-multiplicity of placeholders must match.
        if Counter(original_ph) != Counter(translated_ph):
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
            '"{prompt_template}"\n\n'
            "It is CRITICAL to maintain the exact semantic meaning.\n"
            "It is CRITICAL not to translate placeholders in the format {{PLACEHOLDER}}.\n"
            "It is CRITICAL to preserve the indentation, so:\n"
            "1) Insert a newline character when there is a new line.\n"
            "2) Preserve format {{PLACEHOLDER}}: [sentence] when you encounter it.\n"
            "Return ONLY the translation. DO NOT include any additional explanation or text."
        )
