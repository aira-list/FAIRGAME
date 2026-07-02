"""System-level routes: health, settings, llms, languages, baselines."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from web_api.models import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="OK",
        message="Service is running",
    )


@router.get("/api/settings")
def settings() -> dict[str, str]:
    """Deploy-time UI settings the SPA reads on startup.

    ``community_url`` points the "FAIRGAME community" links at the operator's
    public showcase site; it is empty by default (links are hidden) and set
    via the ``FAIRGAME_COMMUNITY_URL`` environment variable on deploy.

    ``translator_model`` is the default LLM the translate endpoint uses when
    the caller doesn't pick one; the SPA preselects it in the translate dialog
    (set via ``FAIRGAME_TRANSLATOR_MODEL``).
    """
    from web_api.engine import get_engine

    return {
        "community_url": os.getenv("FAIRGAME_COMMUNITY_URL", ""),
        "translator_model": get_engine().default_translator_model,
    }


@router.get("/api/llms")
def list_llms() -> dict[str, list[str]]:
    """Curated, ordered list of models shown in the UI (clean current names).

    Legacy logical names still resolve at run time but are intentionally
    omitted here; any other model can be used via the ``litellm:<model>``
    custom entry. Featured names are filtered to those actually registered.
    """
    from src.llm_connectors import llm_factory_connector

    registered = llm_factory_connector.MODEL_PROVIDER_MAP
    featured = [m for m in llm_factory_connector.FEATURED_MODELS if m in registered]
    return {"llms": featured}


# Top 30 languages by speakers, with a flag emoji and the language code
# the FAIRGAME engine actually accepts. Note the codebase uses "cn" for
# Chinese (not "zh") and "vn" for Vietnamese (not "vi").
_TOP_LANGUAGES: list[dict[str, str]] = [
    {"code": "en", "name": "English", "native": "English", "flag": "🇬🇧"},
    {"code": "cn", "name": "Mandarin", "native": "中文", "flag": "🇨🇳"},
    {"code": "es", "name": "Spanish", "native": "Español", "flag": "🇪🇸"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    {"code": "ar", "name": "Arabic", "native": "العربية", "flag": "🇸🇦"},
    {"code": "bn", "name": "Bengali", "native": "বাংলা", "flag": "🇧🇩"},
    {"code": "pt", "name": "Portuguese", "native": "Português", "flag": "🇵🇹"},
    {"code": "ru", "name": "Russian", "native": "Русский", "flag": "🇷🇺"},
    {"code": "ja", "name": "Japanese", "native": "日本語", "flag": "🇯🇵"},
    {"code": "de", "name": "German", "native": "Deutsch", "flag": "🇩🇪"},
    {"code": "ur", "name": "Urdu", "native": "اُردُو", "flag": "🇵🇰"},
    {"code": "id", "name": "Indonesian", "native": "Bahasa Indonesia", "flag": "🇮🇩"},
    {"code": "fr", "name": "French", "native": "Français", "flag": "🇫🇷"},
    {"code": "tr", "name": "Turkish", "native": "Türkçe", "flag": "🇹🇷"},
    {"code": "ko", "name": "Korean", "native": "한국어", "flag": "🇰🇷"},
    {"code": "vn", "name": "Vietnamese", "native": "Tiếng Việt", "flag": "🇻🇳"},
    {"code": "ta", "name": "Tamil", "native": "தமிழ்", "flag": "🇮🇳"},
    {"code": "te", "name": "Telugu", "native": "తెలుగు", "flag": "🇮🇳"},
    {"code": "mr", "name": "Marathi", "native": "मराठी", "flag": "🇮🇳"},
    {"code": "it", "name": "Italian", "native": "Italiano", "flag": "🇮🇹"},
    {"code": "ms", "name": "Malay", "native": "Bahasa Melayu", "flag": "🇲🇾"},
    {"code": "th", "name": "Thai", "native": "ภาษาไทย", "flag": "🇹🇭"},
    {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી", "flag": "🇮🇳"},
    {"code": "fa", "name": "Persian", "native": "فارسی", "flag": "🇮🇷"},
    {"code": "pl", "name": "Polish", "native": "Polski", "flag": "🇵🇱"},
    {"code": "uk", "name": "Ukrainian", "native": "Українська", "flag": "🇺🇦"},
    {"code": "nl", "name": "Dutch", "native": "Nederlands", "flag": "🇳🇱"},
    {"code": "ro", "name": "Romanian", "native": "Română", "flag": "🇷🇴"},
    {"code": "ha", "name": "Hausa", "native": "Hausa", "flag": "🇳🇬"},
    {"code": "sw", "name": "Swahili", "native": "Kiswahili", "flag": "🇰🇪"},
]


@router.get("/api/languages")
def list_languages() -> dict[str, Any]:
    """Top 30 languages with flags + which ones ship a default template.

    "Shipped" reflects the languages present in the starter library templates.
    """
    from web_api import seeds

    shipped = {t.get("language") for t in seeds.SEED_TEMPLATES if t.get("language")}
    out = []
    for entry in _TOP_LANGUAGES:
        out.append({**entry, "shipped": entry["code"] in shipped})
    return {"languages": out}


@router.get("/api/baselines")
def list_baselines() -> dict[str, list[str]]:
    """Available canonical baseline strategy names."""
    from src.baseline_strategies import available_baselines

    return {"baselines": available_baselines()}
