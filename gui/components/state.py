"""Streamlit ``session_state`` helpers — typed access + theming bootstrap."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from gui.components.fakes import is_demo_active, set_demo_mode

# Where finished runs are written.
RESULTS_DIR = Path(__file__).resolve().parents[2] / "results" / "gui"

# CSS path injected on every page.
CSS_PATH = Path(__file__).resolve().parents[1] / "static" / "style.css"


def init_page(title: str, icon: str = "🎯") -> None:
    """Set page metadata, inject CSS, and lay out the persistent sidebar."""
    st.set_page_config(
        page_title=f"FAIRGAME · {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    if CSS_PATH.is_file():
        css = CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    _ensure_defaults()
    _render_sidebar()


def _ensure_defaults() -> None:
    """Initialise session_state slots once per session."""
    defaults: Dict[str, Any] = {
        "demo_mode": True,
        "config_draft": None,
        "last_run": None,
        "run_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    # Sync the connector registry with the toggle.
    set_demo_mode(st.session_state["demo_mode"])


def _render_sidebar() -> None:
    """Sidebar shared across every page: branding, demo toggle, status."""
    with st.sidebar:
        st.markdown(
            """
            <div class="fg-sidebar-title">🎯 FAIRGAME</div>
            <div class="fg-sidebar-sub">Bias recognition for AI agents through game theory.</div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("##### Mode")
        toggle = st.toggle(
            "Demo mode (no API calls)",
            value=st.session_state.get("demo_mode", True),
            key="_demo_toggle",
            help=(
                "On: all LLM calls are answered by a fast, deterministic stub. "
                "Off: real provider APIs are called — make sure your "
                "API_KEY_* environment variables are set."
            ),
        )
        # Keep canonical state in sync; toggling here propagates to every page.
        if toggle != st.session_state["demo_mode"]:
            st.session_state["demo_mode"] = toggle
            set_demo_mode(toggle)

        if is_demo_active():
            st.markdown(
                "<div class='fg-banner'>Demo mode is on. Results are illustrative — "
                "no provider API is being called.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='fg-banner fg-banner-live'>Live mode. "
                "Provider APIs will be billed for each agent action.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("##### Recent runs")
        history: List[Dict[str, Any]] = st.session_state.get("run_history", [])
        if not history:
            st.caption("No runs yet.")
        else:
            for entry in reversed(history[-5:]):
                st.markdown(
                    f"- **{entry['name']}** &middot; "
                    f"<span style='opacity:0.7'>{entry['timestamp']}</span>",
                    unsafe_allow_html=True,
                )


def get_demo_mode() -> bool:
    return bool(st.session_state.get("demo_mode", True))


def get_config_draft() -> Optional[Dict[str, Any]]:
    return st.session_state.get("config_draft")


def set_config_draft(config: Dict[str, Any]) -> None:
    st.session_state["config_draft"] = config


def get_last_run() -> Optional[Dict[str, Any]]:
    return st.session_state.get("last_run")


def set_last_run(payload: Dict[str, Any]) -> None:
    st.session_state["last_run"] = payload
    history: List[Dict[str, Any]] = st.session_state.setdefault("run_history", [])
    history.append(
        {
            "name": payload.get("name", "(unnamed)"),
            "timestamp": payload.get("timestamp", ""),
            "path": str(payload.get("output_dir", "")),
        }
    )
