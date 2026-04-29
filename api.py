"""HTTP API for FAIRGAME.

The Flask app exposes three endpoints:

* ``POST /create_and_run_games`` — run a game configuration and return results.
* ``POST /translate_template``   — translate a prompt template into a target language.
* ``GET  /health``               — liveness probe.

Results may optionally be uploaded to an S3-compatible bucket; when S3 is not
configured the upload step is silently skipped and the service still returns
the in-memory results to the caller.
"""

from __future__ import annotations

import os
import posixpath
from datetime import datetime
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from src.fairgame_factory import FairGameFactory
from src.results_processing.results_processor import ResultsProcessor
from src.template_translation.template_translator import TemplateTranslator
from src.utils.logger import configure_logging, get_logger
from src.utils.utils import (
    deduplicate_preserving_order,
    remove_duplicate_prefix,
    slug,
)

configure_logging()
logger = get_logger(__name__)


class S3Uploader:
    """Uploads result CSVs to an S3-compatible store. No-ops when unconfigured."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("S3_ENDPOINT")
        self.bucket_name = os.getenv("BUCKET_NAME")
        self.key = os.getenv("S3_KEY")
        self.secret = os.getenv("S3_SECRET")
        self.prefix = (os.getenv("S3_PREFIX") or "").strip("/")
        logger.info(
            "S3 uploader initialised (configured=%s bucket=%r prefix=%r endpoint=%r)",
            self.is_configured(),
            self.bucket_name,
            self.prefix,
            self.endpoint,
        )

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.bucket_name and self.key and self.secret)

    def get_s3_credentials(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "secret": self.secret,
            "client_kwargs": {"endpoint_url": self.endpoint},
        }

    def _build_key(self, filepath: str) -> str:
        clean = filepath.lstrip("/")
        if self.prefix:
            return posixpath.join(self.prefix, clean)
        return clean

    def save(self, dataframe: pd.DataFrame, filepath: str) -> Optional[str]:
        if not self.is_configured():
            logger.info("S3 not configured; skipping upload (would have written %s).", filepath)
            return None
        storage_options = self.get_s3_credentials()
        key = self._build_key(filepath)
        url = f"s3://{self.bucket_name}/{key}"
        try:
            dataframe.to_csv(
                url,
                index=False,
                sep=";",
                quotechar='"',
                quoting=1,
                storage_options=storage_options,
                encoding="utf_8",
            )
        except Exception:
            logger.exception("S3 upload to %s failed", url)
            raise
        logger.info("Uploaded results to %s", url)
        return url


class ConfigurationError(ValueError):
    """Raised when the API receives an invalid configuration payload."""


class FairGameAPI:
    """Glue between the HTTP layer and the FAIRGAME engine."""

    DEFAULT_FOLDER = os.getenv("DEFAULT_FOLDER", "fairgame-results")

    def __init__(
        self,
        uploader: S3Uploader,
        translator: Optional[TemplateTranslator] = None,
    ) -> None:
        self.uploader = uploader
        self.results_processor = ResultsProcessor()
        self._translator = translator
        self._translator_model = os.getenv("FAIRGAME_TRANSLATOR_MODEL", "OpenAIGPT4o")

    @property
    def template_translator(self) -> TemplateTranslator:
        if self._translator is None:
            self._translator = TemplateTranslator(self._translator_model)
        return self._translator

    # ---- Endpoint handlers ----------------------------------------------

    def create_and_run_games(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run games described by ``config`` and persist the results."""
        if not isinstance(config, dict):
            raise ConfigurationError("Request body must be a JSON object.")
        self._validate_llms_config(config)

        models_tag = self._create_models_tag(config)
        outcomes = self._run_games(config)
        df = self._process_results(outcomes)
        results_filepath = self._build_results_filepath(config, models_tag)

        self.uploader.save(df, results_filepath)
        return df.to_dict(orient="records")

    def translate_template(
        self, text: str, target_lang: str, cosine_threshold: float = 0.6
    ) -> str:
        return self.template_translator.translate(
            text, target_lang, cosine_threshold=cosine_threshold
        )

    def health_check(self) -> Dict[str, str]:
        return {"status": "OK", "message": "Service is running"}

    # ---- Internals ------------------------------------------------------

    def _validate_llms_config(self, config: Dict[str, Any]) -> None:
        if "llms" in config:
            llms = config.get("llms")
            if not isinstance(llms, (list, dict)):
                raise ConfigurationError(
                    "'llms' must be a list of model names or a dict {agent_name: model}."
                )
        elif "llm" in config:
            if not isinstance(config["llm"], str) or not config["llm"]:
                raise ConfigurationError("'llm' must be a non-empty string.")
        else:
            raise ConfigurationError("Configuration must include 'llm' or 'llms'.")

    def _extract_models(self, llms_field: Any) -> List[str]:
        if isinstance(llms_field, dict):
            iterable: Iterable[Any] = llms_field.values()
        else:
            iterable = llms_field or []
        return [v for v in iterable if isinstance(v, str) and v.strip()]

    def _create_models_tag(self, config: Dict[str, Any]) -> str:
        llms = config.get("llms") if "llms" in config else [config.get("llm")]
        models = self._extract_models(llms)
        if not models:
            raise ConfigurationError("No valid models found in configuration.")
        unique = deduplicate_preserving_order(models)
        return "-".join(slug(m) for m in unique) or "mixed"

    def _run_games(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return FairGameFactory().create_and_run_games(config)

    def _process_results(self, outcomes: Dict[str, Any]) -> pd.DataFrame:
        return self.results_processor.process(outcomes)

    def _get_game_names(self, config: Dict[str, Any]) -> Tuple[str, str]:
        full_game_name = slug(config.get("name", "game"))
        parts = [p for p in full_game_name.split("-") if p]
        short_game_name = (
            "-".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "game")
        )
        return full_game_name, short_game_name

    def _build_results_filepath(self, config: Dict[str, Any], models_tag: str) -> str:
        current_date = datetime.now().strftime("%Y%m%d")
        full_game_name, short_game_name = self._get_game_names(config)
        file_base = remove_duplicate_prefix(full_game_name, short_game_name)
        return (
            f"{self.DEFAULT_FOLDER}/"
            f"{models_tag}/"
            f"{current_date}_{short_game_name}/"
            f"{file_base}.csv"
        )


# ---- Flask wiring -------------------------------------------------------

def create_app(api: Optional[FairGameAPI] = None) -> Flask:
    """Application factory; ``create_app()`` is what gunicorn imports."""
    app = Flask(__name__)
    api = api or FairGameAPI(S3Uploader())

    @app.route("/create_and_run_games", methods=["POST"])
    def create_and_run_games_route():
        config = request.get_json(silent=True)
        if config is None:
            return jsonify({"error": "Request must include a JSON body."}), HTTPStatus.BAD_REQUEST
        return jsonify(api.create_and_run_games(config)), HTTPStatus.OK

    @app.route("/health", methods=["GET"])
    def health_check_route():
        return jsonify(api.health_check()), HTTPStatus.OK

    @app.route("/translate_template", methods=["POST"])
    def translate_route():
        data = request.get_json(silent=True) or {}
        text = data.get("template")
        target_lang = data.get("lang_to")
        try:
            cosine_threshold = float(data.get("cosine_threshold", 0.6))
        except (TypeError, ValueError):
            return (
                jsonify({"error": "cosine_threshold must be a number."}),
                HTTPStatus.BAD_REQUEST,
            )

        if not text or not target_lang:
            return (
                jsonify({"error": "Missing 'template' or 'lang_to' in request"}),
                HTTPStatus.BAD_REQUEST,
            )

        translated = api.translate_template(text, target_lang, cosine_threshold)
        return jsonify({"translated_text": translated}), HTTPStatus.OK

    @app.errorhandler(ConfigurationError)
    def _on_configuration_error(exc: ConfigurationError):
        logger.warning("Rejected request: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    @app.errorhandler(ValueError)
    def _on_value_error(exc: ValueError):
        logger.warning("Rejected request: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    @app.errorhandler(TypeError)
    def _on_type_error(exc: TypeError):
        # Pydantic config validation re-raises invalid configs as TypeError.
        logger.warning("Rejected request: %s", exc)
        return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

    @app.errorhandler(HTTPException)
    def _on_http_error(exc: HTTPException):
        return jsonify({"error": exc.description}), exc.code

    @app.errorhandler(Exception)
    def _on_unexpected_error(exc: Exception):
        logger.exception("Unhandled error processing request")
        return (
            jsonify({"error": f"Unexpected error: {exc}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port)
