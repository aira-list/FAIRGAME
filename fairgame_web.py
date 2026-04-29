"""FAIRGAME web app: FastAPI backend + vanilla static frontend.

Run with::

    uvicorn fairgame_web:app --reload

Then open http://localhost:8000.

Replaces the old Flask ``api.py`` and the Streamlit ``gui/`` app:

* The same three HTTP routes (``/health``, ``/create_and_run_games``,
  ``/translate_template``) live on under ``/api/...``, with the original
  paths preserved as redirects for backwards compatibility with any
  existing clients.
* Additional endpoints power the new SPA: ``/api/presets``,
  ``/api/runs`` (POST and GET-list), ``/api/runs/{id}``.
* Static files in ``./web`` are served at ``/``; visiting the root in a
  browser loads the SPA.
"""

from __future__ import annotations

import json
import os
import posixpath
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.demo_connector import is_demo_active, set_demo_mode
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

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
RESOURCES_DIR = PROJECT_ROOT / "resources"
RUNS_DIR = PROJECT_ROOT / "results" / "web"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# S3 uploader (carried over from api.py — same behaviour)
# ---------------------------------------------------------------------------


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

    def _credentials(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "secret": self.secret,
            "client_kwargs": {"endpoint_url": self.endpoint},
        }

    def _build_key(self, filepath: str) -> str:
        clean = filepath.lstrip("/")
        return posixpath.join(self.prefix, clean) if self.prefix else clean

    def save(self, df: pd.DataFrame, filepath: str) -> Optional[str]:
        if not self.is_configured():
            logger.info(
                "S3 not configured; skipping upload (would have written %s).", filepath
            )
            return None
        key = self._build_key(filepath)
        url = f"s3://{self.bucket_name}/{key}"
        try:
            df.to_csv(url, index=False, storage_options=self._credentials())
            logger.info("Uploaded results to %s", url)
            return url
        except Exception:  # noqa: BLE001 — surface as a soft failure
            logger.exception("Failed to upload results to S3")
            return None


# ---------------------------------------------------------------------------
# Engine wrapper (mirrors api.py:FairGameAPI but trimmed for the new API)
# ---------------------------------------------------------------------------


class FairGameEngine:
    """Wraps :class:`FairGameFactory` and the results processor."""

    DEFAULT_FOLDER = os.getenv("DEFAULT_FOLDER", "fairgame-results")

    def __init__(
        self,
        uploader: Optional[S3Uploader] = None,
        translator: Optional[TemplateTranslator] = None,
    ) -> None:
        self.uploader = uploader or S3Uploader()
        self.results_processor = ResultsProcessor()
        self._translator = translator
        self._translator_model = os.getenv("FAIRGAME_TRANSLATOR_MODEL", "OpenAIGPT4o")

    @property
    def template_translator(self) -> TemplateTranslator:
        if self._translator is None:
            self._translator = TemplateTranslator(self._translator_model)
        return self._translator

    def create_and_run_games(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(config, dict):
            raise ValueError("Request body must be a JSON object.")
        self._validate_llms_config(config)
        models_tag = self._models_tag(config)
        outcomes = FairGameFactory().create_and_run_games(config)
        df = self.results_processor.process(outcomes)
        self.uploader.save(df, self._results_filepath(config, models_tag))
        return df.to_dict(orient="records")

    @staticmethod
    def _validate_llms_config(config: Dict[str, Any]) -> None:
        if "llms" in config:
            if not isinstance(config["llms"], (list, dict)):
                raise ValueError(
                    "'llms' must be a list of model names or a dict {agent_name: model}."
                )
        elif "llm" in config:
            if not isinstance(config["llm"], str) or not config["llm"]:
                raise ValueError("'llm' must be a non-empty string.")
        else:
            raise ValueError("Configuration must include 'llm' or 'llms'.")

    @staticmethod
    def _extract_models(llms_field: Any) -> List[str]:
        iterable: Iterable[Any] = (
            llms_field.values() if isinstance(llms_field, dict) else (llms_field or [])
        )
        return [v for v in iterable if isinstance(v, str) and v.strip()]

    def _models_tag(self, config: Dict[str, Any]) -> str:
        llms = config.get("llms") if "llms" in config else [config.get("llm")]
        models = self._extract_models(llms)
        if not models:
            raise ValueError("No valid models found in configuration.")
        return "-".join(slug(m) for m in deduplicate_preserving_order(models)) or "mixed"

    @staticmethod
    def _game_names(config: Dict[str, Any]) -> Tuple[str, str]:
        full = slug(config.get("name", "game"))
        parts = [p for p in full.split("-") if p]
        short = "-".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "game")
        return full, short

    def _results_filepath(self, config: Dict[str, Any], models_tag: str) -> str:
        date = datetime.now().strftime("%Y%m%d")
        full, short = self._game_names(config)
        base = remove_duplicate_prefix(full, short)
        return f"{self.DEFAULT_FOLDER}/{models_tag}/{date}_{short}/{base}.csv"


# ---------------------------------------------------------------------------
# Run-history persistence (used by /api/runs)
# ---------------------------------------------------------------------------


def _save_run(
    run_id: str,
    config: Dict[str, Any],
    rows: List[Dict[str, Any]],
    *,
    demo_mode: bool,
) -> Path:
    """Write a run's metadata + CSV payload to ``RUNS_DIR/<run_id>/``."""
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "results.csv", index=False)
    metadata = {
        "id": run_id,
        "name": config.get("name", "(unnamed)"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "demo_mode": demo_mode,
        "config": config,
        "n_rows": len(rows),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return run_dir


def _list_runs() -> List[Dict[str, Any]]:
    runs: List[Dict[str, Any]] = []
    if not RUNS_DIR.is_dir():
        return runs
    for child in sorted(RUNS_DIR.iterdir(), reverse=True):
        meta_file = child / "metadata.json"
        if not meta_file.is_file():
            continue
        try:
            runs.append(json.loads(meta_file.read_text()))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed run metadata at %s", meta_file)
    return runs


def _load_run(run_id: str) -> Dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    meta_file = run_dir / "metadata.json"
    csv_file = run_dir / "results.csv"
    if not meta_file.is_file() or not csv_file.is_file():
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    metadata = json.loads(meta_file.read_text())
    rows = pd.read_csv(csv_file).to_dict(orient="records")
    return {**metadata, "rows": rows}


# ---------------------------------------------------------------------------
# Preset discovery (used by /api/presets)
# ---------------------------------------------------------------------------


def _variant_suffix_from_stem(stem: str, category: str) -> str:
    """Derive a human-readable parameter suffix from the file stem.

    E.g. ``prisoner_dilemma_round_known_harsh`` (in category
    ``prisoner_dilemma``) → ``"round-known, harsh"``. The category prefix
    is stripped so only the differentiating parameters survive.
    """
    parts = stem.split("_")
    cat_parts = category.split("_")
    # Strip the leading category prefix tokens.
    i = 0
    while i < len(parts) and i < len(cat_parts) and parts[i] == cat_parts[i]:
        i += 1
    rest = parts[i:]
    if not rest:
        return ""
    # Heuristic regroup: "round_known" / "round_not_known" stay glued.
    label = " ".join(rest)
    label = label.replace(" round known", "round-known").replace(
        " round not known", "round-not-known"
    )
    label = label.replace("round known", "round-known").replace(
        "round not known", "round-not-known"
    )
    return ", ".join(t.strip() for t in label.split() if t.strip()).replace(
        "round-known", "round-known"
    )


def _discover_presets() -> List[Dict[str, Any]]:
    """Walk ``resources/config/<category>/<name>.json`` and return summaries.

    Each preset gets a disambiguating ``label`` derived from the file
    stem, so multiple variants of the same game (different round-known
    flags, different payoff weights, …) don't all collapse into the
    same dropdown entry.
    """
    config_root = RESOURCES_DIR / "config"
    if not config_root.is_dir():
        return []
    presets: List[Dict[str, Any]] = []
    for category_dir in sorted(p for p in config_root.iterdir() if p.is_dir()):
        for json_file in sorted(category_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text())
            except json.JSONDecodeError:
                logger.warning("Skipping malformed preset %s", json_file)
                continue
            name = data.get("name", json_file.stem)
            variant = _variant_suffix_from_stem(json_file.stem, category_dir.name)
            label = f"{name} ({variant})" if variant else name
            presets.append(
                {
                    "id": f"{category_dir.name}/{json_file.stem}",
                    "category": category_dir.name,
                    "name": name,
                    "label": label,
                    "languages": data.get("languages") or [],
                    "n_rounds": data.get("nRounds"),
                    "agents": list((data.get("agents") or {}).get("names") or []),
                    "path": str(json_file.relative_to(PROJECT_ROOT)),
                }
            )
    return presets


def _load_preset(preset_id: str) -> Dict[str, Any]:
    config_root = RESOURCES_DIR / "config"
    target = config_root / f"{preset_id}.json"
    if not target.is_file() or config_root not in target.parents:
        raise HTTPException(status_code=404, detail=f"Preset {preset_id!r} not found.")
    return json.loads(target.read_text())


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------


class TranslateBody(BaseModel):
    template: str
    lang_to: str
    cosine_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class RunBody(BaseModel):
    """Either an inline config or a preset id, plus the demo-mode flag."""

    config: Optional[Dict[str, Any]] = None
    preset: Optional[str] = None
    demo_mode: bool = True


class HealthResponse(BaseModel):
    status: str
    message: str
    demo_mode: bool


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


app = FastAPI(title="FAIRGAME", version="0.2.0")

engine = FairGameEngine()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="OK",
        message="Service is running",
        demo_mode=is_demo_active(),
    )


@app.post("/api/translate")
def translate(body: TranslateBody) -> Dict[str, str]:
    if not body.template or not body.lang_to:
        raise HTTPException(
            status_code=400, detail="Missing 'template' or 'lang_to'."
        )
    translated = engine.template_translator.translate(
        body.template, body.lang_to, cosine_threshold=body.cosine_threshold
    )
    return {"translated_text": translated}


@app.get("/api/presets")
def presets() -> Dict[str, Any]:
    items = _discover_presets()
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for p in items:
        by_category.setdefault(p["category"], []).append(p)
    return {"presets": items, "by_category": by_category}


@app.get("/api/presets/{preset_id:path}")
def preset_detail(preset_id: str) -> Dict[str, Any]:
    return _load_preset(preset_id)


@app.post("/api/runs")
def create_run(body: RunBody) -> Dict[str, Any]:
    config = body.config
    if config is None and body.preset:
        config = _load_preset(body.preset)
    if config is None:
        raise HTTPException(
            status_code=400, detail="Provide either 'config' or 'preset'."
        )

    set_demo_mode(body.demo_mode)
    try:
        rows = engine.create_and_run_games(config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TypeError as exc:
        # Pydantic config validation re-raises invalid configs as TypeError.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = uuid.uuid4().hex[:12]
    _save_run(run_id, config, rows, demo_mode=body.demo_mode)
    return {"id": run_id, "rows": rows}


@app.get("/api/runs")
def list_runs() -> Dict[str, Any]:
    return {"runs": _list_runs()}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> Dict[str, Any]:
    return _load_run(run_id)


@app.get("/api/runs/{run_id}/csv")
def run_csv(run_id: str) -> FileResponse:
    csv_file = RUNS_DIR / run_id / "results.csv"
    if not csv_file.is_file():
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    return FileResponse(
        csv_file, media_type="text/csv", filename=f"fairgame_run_{run_id}.csv"
    )


@app.get("/api/llms")
def list_llms() -> Dict[str, List[str]]:
    """Available LLM model names registered in the connector factory."""
    from src.llm_connectors import llm_factory_connector

    return {"llms": sorted(llm_factory_connector.MODEL_PROVIDER_MAP.keys())}


# Top 30 languages by speakers, with a flag emoji and the language code
# the FAIRGAME engine actually accepts. Note the codebase uses "cn" for
# Chinese (not "zh") and "vn" for Vietnamese (not "vi").
_TOP_LANGUAGES: List[Dict[str, str]] = [
    {"code": "en", "name": "English",      "native": "English",        "flag": "🇬🇧"},
    {"code": "cn", "name": "Mandarin",     "native": "中文",           "flag": "🇨🇳"},
    {"code": "es", "name": "Spanish",      "native": "Español",         "flag": "🇪🇸"},
    {"code": "hi", "name": "Hindi",        "native": "हिन्दी",          "flag": "🇮🇳"},
    {"code": "ar", "name": "Arabic",       "native": "العربية",         "flag": "🇸🇦"},
    {"code": "bn", "name": "Bengali",      "native": "বাংলা",          "flag": "🇧🇩"},
    {"code": "pt", "name": "Portuguese",   "native": "Português",       "flag": "🇵🇹"},
    {"code": "ru", "name": "Russian",      "native": "Русский",         "flag": "🇷🇺"},
    {"code": "ja", "name": "Japanese",     "native": "日本語",         "flag": "🇯🇵"},
    {"code": "de", "name": "German",       "native": "Deutsch",         "flag": "🇩🇪"},
    {"code": "ur", "name": "Urdu",         "native": "اُردُو",          "flag": "🇵🇰"},
    {"code": "id", "name": "Indonesian",   "native": "Bahasa Indonesia","flag": "🇮🇩"},
    {"code": "fr", "name": "French",       "native": "Français",        "flag": "🇫🇷"},
    {"code": "tr", "name": "Turkish",      "native": "Türkçe",          "flag": "🇹🇷"},
    {"code": "ko", "name": "Korean",       "native": "한국어",         "flag": "🇰🇷"},
    {"code": "vn", "name": "Vietnamese",   "native": "Tiếng Việt",      "flag": "🇻🇳"},
    {"code": "ta", "name": "Tamil",        "native": "தமிழ்",          "flag": "🇮🇳"},
    {"code": "te", "name": "Telugu",       "native": "తెలుగు",         "flag": "🇮🇳"},
    {"code": "mr", "name": "Marathi",      "native": "मराठी",          "flag": "🇮🇳"},
    {"code": "it", "name": "Italian",      "native": "Italiano",        "flag": "🇮🇹"},
    {"code": "ms", "name": "Malay",        "native": "Bahasa Melayu",   "flag": "🇲🇾"},
    {"code": "th", "name": "Thai",         "native": "ภาษาไทย",        "flag": "🇹🇭"},
    {"code": "gu", "name": "Gujarati",     "native": "ગુજરાતી",         "flag": "🇮🇳"},
    {"code": "fa", "name": "Persian",      "native": "فارسی",           "flag": "🇮🇷"},
    {"code": "pl", "name": "Polish",       "native": "Polski",          "flag": "🇵🇱"},
    {"code": "uk", "name": "Ukrainian",    "native": "Українська",      "flag": "🇺🇦"},
    {"code": "nl", "name": "Dutch",        "native": "Nederlands",      "flag": "🇳🇱"},
    {"code": "ro", "name": "Romanian",     "native": "Română",          "flag": "🇷🇴"},
    {"code": "ha", "name": "Hausa",        "native": "Hausa",           "flag": "🇳🇬"},
    {"code": "sw", "name": "Swahili",      "native": "Kiswahili",       "flag": "🇰🇪"},
]


@app.get("/api/languages")
def list_languages() -> Dict[str, Any]:
    """Top 30 languages with flags + which ones ship a default template.

    A language is "templated" when at least one ``*_<code>.txt`` /
    ``*_<code>.rtf`` exists under ``resources/game_templates/``. For
    non-templated languages the user must run ``/api/translate`` first
    or accept that the engine will fail to load a template.
    """
    template_dir = RESOURCES_DIR / "game_templates"
    shipped: set = set()
    if template_dir.is_dir():
        for f in template_dir.iterdir():
            if not f.is_file():
                continue
            stem = f.stem
            if "_" in stem:
                shipped.add(stem.rsplit("_", 1)[1])
    out = []
    for entry in _TOP_LANGUAGES:
        out.append({**entry, "shipped": entry["code"] in shipped})
    return {"languages": out}


@app.get("/api/baselines")
def list_baselines() -> Dict[str, List[str]]:
    """Available canonical baseline strategy names."""
    from src.baseline_strategies import _REGISTRY  # noqa: SLF001 — internal but stable

    return {"baselines": sorted(_REGISTRY.keys())}


class CompareBody(BaseModel):
    run_a: str
    run_b: str
    metrics: Optional[List[str]] = None
    correction: str = Field(default="none")


@app.post("/api/runs/compare")
def compare_runs(body: CompareBody) -> Dict[str, Any]:
    """Welch + Mann-Whitney comparison between two persisted runs."""
    from src.results_processing.stats import (
        compare_metrics,
        default_comparison_metrics,
    )

    csv_a = RUNS_DIR / body.run_a / "results.csv"
    csv_b = RUNS_DIR / body.run_b / "results.csv"
    if not csv_a.is_file() or not csv_b.is_file():
        raise HTTPException(status_code=404, detail="One or both runs not found.")
    df_a = pd.read_csv(csv_a)
    df_b = pd.read_csv(csv_b)
    metrics = body.metrics or sorted(
        set(default_comparison_metrics(df_a) + default_comparison_metrics(df_b))
    )
    if not metrics:
        return {"metrics": [], "rows": []}
    result = compare_metrics(df_a, df_b, metrics, correction=body.correction)
    return {"metrics": metrics, "rows": result.to_dict(orient="records")}


# ---- Backwards-compatible Flask paths -----------------------------------
# Old clients hitting /create_and_run_games, /translate_template, /health
# get a 308 redirect to the new /api/* equivalents. Each legacy path is
# explicit so the SPA catch-all below isn't shadowed.


def _legacy_redirect(target: str) -> JSONResponse:
    return JSONResponse(
        status_code=308,
        content={"redirect": target, "message": f"Use {target} (FastAPI) instead."},
        headers={"Location": target},
    )


@app.get("/health", include_in_schema=False)
def legacy_health() -> JSONResponse:
    return _legacy_redirect("/api/health")


@app.api_route("/create_and_run_games", methods=["GET", "POST"], include_in_schema=False)
def legacy_create_and_run_games() -> JSONResponse:
    return _legacy_redirect("/api/runs")


@app.api_route("/translate_template", methods=["GET", "POST"], include_in_schema=False)
def legacy_translate_template() -> JSONResponse:
    return _legacy_redirect("/api/translate")


# ---- Static SPA mount ---------------------------------------------------
# Catch-all serves index.html so client-side routes work.

_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}


if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    @app.get("/", include_in_schema=False)
    def root() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", headers=_NO_CACHE)

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        # Direct file under web/ wins; everything else falls back to the SPA.
        target = WEB_DIR / path
        if target.is_file():
            return FileResponse(target, headers=_NO_CACHE)
        return FileResponse(WEB_DIR / "index.html", headers=_NO_CACHE)
else:
    @app.get("/", include_in_schema=False)
    def root_no_web() -> Dict[str, str]:
        return {
            "message": (
                "FAIRGAME API is running but the static frontend "
                f"({WEB_DIR}) is missing."
            ),
        }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("fairgame_web:app", host="0.0.0.0", port=port, reload=True)
