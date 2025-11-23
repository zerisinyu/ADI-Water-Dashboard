from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlencode

import streamlit as st

from utils import get_zones, prepare_service_data
from llm import ChatLLM, LLMNotConfiguredError

# Scenes are implemented in src_page/*
from src_page.exec import scene_executive as scene_exec_page
from src_page.access import scene_access
from src_page.quality import scene_quality as scene_quality_page
from src_page.finance import scene_finance as scene_finance_page
from src_page.production import scene_production as scene_production_page
from src_page.governance import scene_governance as scene_governance_page
from src_page.sector import scene_sector as scene_sector_page


def _inject_styles() -> None:
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def _chat_enabled() -> bool:
    try:
        flag = st.secrets.get("ENABLE_CHAT_WIDGET", os.getenv("ENABLE_CHAT_WIDGET", "true"))
    except Exception:
        flag = os.getenv("ENABLE_CHAT_WIDGET", "true")
    return str(flag).lower() in {"1", "true", "yes", "on"}


def _get_query_param(name: str, default: Optional[str] = None) -> Optional[str]:
    # Streamlit added st.query_params in newer versions; fall back to experimental APIs
    try:  # modern
        return st.query_params.get(name, default)  # type: ignore[attr-defined]
    except Exception:
        params = st.experimental_get_query_params()
        values = params.get(name)
        return values[0] if values else default


def _set_query_param(name: str, value: Optional[str]) -> None:
    try:
        if value is None:
            # Clear the param
            qp = dict(st.query_params)  # type: ignore[attr-defined]
            qp.pop(name, None)
            st.query_params.clear()
            for k, v in qp.items():
                st.query_params[k] = v
        else:
            st.query_params[name] = value  # type: ignore[attr-defined]
    except Exception:
        params = st.experimental_get_query_params()
        if value is None:
            params.pop(name, None)
            st.experimental_set_query_params(**params)
        else:
            params[name] = value
            st.experimental_set_query_params(**params)


def _build_chat_open_href() -> str:
    try:
        params = dict(st.query_params)  # type: ignore[attr-defined]
    except Exception:
        params = st.experimental_get_query_params()
    params["chat"] = "open"
    return "?" + urlencode(params, doseq=True)


def _ensure_chat_state() -> None:
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant for the Water Utility Performance Dashboard. "
                    "Answer succinctly and refer to metrics, filters, and scenes when helpful."
                ),
            }
        ]


def _render_chat_fab() -> None:
    if not _chat_enabled():
        return
    href = _build_chat_open_href()
    st.markdown(
        f"<a target=\"_self\" rel=\"noopener\" href=\"{href}\" class=\"chat-fab\" title=\"Chat with assistant\" aria-label=\"Open chat\">💬</a>",
        unsafe_allow_html=True,
    )


def _render_chat_panel_sidebar() -> None:
    """Render a simple chat experience inside the sidebar when chat is open.
    This avoids brittle HTML nesting while providing a reliable UX.
    """
    _ensure_chat_state()
    messages: List[Dict[str, str]] = st.session_state["chat_messages"]

    with st.sidebar:
        st.markdown(
            "<div class='chat-sidebar-header'><h3 style='margin:0'>Assistant</h3>"
            "<a class='chat-close-link' href='?'>Close</a></div>",
            unsafe_allow_html=True,
        )

        # Render history (skip system prompt)
        for m in messages:
            role = m.get("role")
            if role == "system":
                continue
            content = m.get("content", "")
            css_class = "chat-bubble--user" if role == "user" else "chat-bubble--assistant"
            st.markdown(
                f"<div class='chat-bubble {css_class}'>{content}</div>",
                unsafe_allow_html=True,
            )

        # Input + actions in a form so we can clear on submit safely
        with st.form("chat_form_sidebar", clear_on_submit=True):
            prompt = st.text_area(
                "Ask a question",
                key="chat_input_text_sidebar",
                height=90,
                placeholder="Ask about metrics, filters, or data…",
            )
            send_clicked = st.form_submit_button("Send", use_container_width=True)

        if st.button("Close", key="sidebar_close_btn", use_container_width=True):
            _set_query_param("chat", None)
            st.rerun()

        if send_clicked:
            text = (prompt or "").strip()
            if not text:
                st.warning("Please enter a question.")
            else:
                # Simple per-session turn limit
                max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
                user_turns = sum(1 for m in messages if m.get("role") == "user")
                if user_turns >= max_turns:
                    st.warning("You have reached the chat limit for this session.")
                    return
                messages.append({"role": "user", "content": text})
                # Keep history short
                try:
                    client = ChatLLM()
                except LLMNotConfiguredError as e:
                    st.error(str(e))
                    return
                trimmed = ChatLLM.trim_history(messages, max_messages=16)

                # Streaming response into a placeholder
                placeholder = st.empty()
                acc = ""
                try:
                    for chunk in client.stream_chat(trimmed):
                        acc += chunk
                        placeholder.markdown(
                            f"<div class='chat-bubble chat-bubble--assistant'>{acc}</div>",
                            unsafe_allow_html=True,
                        )
                except Exception as e:
                    st.error(f"Chat error: {e}")
                    return

                messages.append({"role": "assistant", "content": acc})
                st.rerun()


def _render_chat_modal_body(input_key_suffix: str = "") -> None:
    """Render the chat UI in the current context (used by modal)."""
    _ensure_chat_state()
    messages: List[Dict[str, str]] = st.session_state["chat_messages"]

    st.markdown(
        "<div class='chat-sidebar-header'><h3 style='margin:0'>Assistant</h3>"
        "<a class='chat-close-link' href='?'>Close</a></div>",
        unsafe_allow_html=True,
    )

    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        content = m.get("content", "")
        css_class = "chat-bubble--user" if role == "user" else "chat-bubble--assistant"
        st.markdown(
            f"<div class='chat-bubble {css_class}'>{content}</div>",
            unsafe_allow_html=True,
        )

    with st.form(f"chat_form_modal{input_key_suffix}", clear_on_submit=True):
        prompt = st.text_area(
            "Ask a question",
            key=f"chat_input_text{input_key_suffix}",
            height=90,
            placeholder="Ask about metrics, filters, or data…",
        )
        send_clicked = st.form_submit_button("Send")

    if st.button("Close", key=f"close_btn{input_key_suffix}"):
        _set_query_param("chat", None)
        st.rerun()

    if send_clicked:
        text = (prompt or "").strip()
        if not text:
            st.warning("Please enter a question.")
        else:
            max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
            user_turns = sum(1 for m in messages if m.get("role") == "user")
            if user_turns >= max_turns:
                st.warning("You have reached the chat limit for this session.")
                return
            messages.append({"role": "user", "content": text})
            try:
                client = ChatLLM()
            except LLMNotConfiguredError as e:
                st.error(str(e))
                return
            trimmed = ChatLLM.trim_history(messages, max_messages=16)
            placeholder = st.empty()
            acc = ""
            try:
                for chunk in client.stream_chat(trimmed):
                    acc += chunk
                    placeholder.markdown(
                        f"<div class='chat-bubble chat-bubble--assistant'>{acc}</div>",
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.error(f"Chat error: {e}")
                return
            messages.append({"role": "assistant", "content": acc})
            st.rerun()


def _render_overview_banner() -> None:
    zone = st.session_state.get("selected_zone")
    country = st.session_state.get("selected_country")
    
    if zone and zone != 'All':
        location_label = f"{zone}, {country}" if country and country != 'All' else zone
    elif country and country != 'All':
        location_label = country
    else:
        location_label = "All Locations"
        
    month = st.session_state.get("selected_month") or "All"
    year = st.session_state.get("selected_year") or "All"

    st.title("Water Utility Performance Dashboard")
    st.caption(f"Overview for {location_label} | Year: {year} | Month: {month}")


def _sidebar_filters() -> None:
    st.sidebar.title("Filters")
    
    # Load data for filters (using service data as it has the most granular time/location info)
    service_data = prepare_service_data()
    df_service = service_data["full_data"]
    
    # 1. Country
    countries = ['All'] + service_data["countries"]
    # Initialize session state if not present
    if "selected_country" not in st.session_state:
        st.session_state["selected_country"] = "All"
        
    selected_country = st.sidebar.selectbox('Country', countries, key='selected_country')

    # 2. Zone
    if selected_country != 'All':
        zones = ['All'] + sorted(df_service[df_service['country'] == selected_country]['zone'].unique().tolist())
    else:
        zones = ['All'] + service_data["zones"]
        
    if "selected_zone" not in st.session_state:
        st.session_state["selected_zone"] = "All"
        
    selected_zone = st.sidebar.selectbox('Zone', zones, key='selected_zone')

    # 3. Year
    available_years = sorted(df_service['year'].unique(), reverse=True)
    if "selected_year" not in st.session_state:
        st.session_state["selected_year"] = available_years[0] if available_years else None
        
    selected_year = st.sidebar.selectbox('Year', available_years, key='selected_year')

    # 4. Month
    months = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    if "selected_month" not in st.session_state:
        st.session_state["selected_month"] = "All"
        
    selected_month_name = st.sidebar.selectbox('Month', months, key='selected_month')

    if st.sidebar.button("Reset filters"):
        st.session_state["selected_country"] = "All"
        st.session_state["selected_zone"] = "All"
        if available_years:
            st.session_state["selected_year"] = available_years[0]
        st.session_state["selected_month"] = "All"
        st.rerun()


def render_uhn_dashboard() -> None:
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
    _inject_styles()
    _sidebar_filters()

    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    _render_overview_banner()

    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    if scene_exec_page:
        scene_exec_page()
    else:
        st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Chat launcher + panel/modal
    if _chat_enabled():
        _render_chat_fab()
        chat_param = (_get_query_param("chat") or "").lower()
        # Prefer modal positioned bottom-right (CSS override). If not supported, fallback to sidebar.
        chat_shown = False
        try:
            dialog_fn = getattr(st, "dialog")  # type: ignore[attr-defined]
        except Exception:
            dialog_fn = getattr(st, "experimental_dialog", None)
        if dialog_fn and chat_param == "open":
            # Some Streamlit versions don't support width argument on dialog
            try:
                decorator = dialog_fn("Assistant", width="small")  # type: ignore[misc]
            except TypeError:
                decorator = dialog_fn("Assistant")

            @decorator  # type: ignore[misc]
            def _chat_modal():
                _render_chat_modal_body("_modal")

            _chat_modal()
            chat_shown = True

        if not chat_shown and chat_param == "open":
            # Fallback to sidebar rendering
            _render_chat_panel_sidebar()


def render_scene_page(scene_key: str) -> None:
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
    _inject_styles()
    _sidebar_filters()
    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    _render_overview_banner()
    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    if scene_key == "exec":
        if scene_exec_page:
            scene_exec_page()
        else:
            st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")
    elif scene_key == "access":
        scene_access()
    elif scene_key == "quality":
        scene_quality_page()
    elif scene_key == "finance":
        scene_finance_page()
    elif scene_key == "production":
        scene_production_page()
    elif scene_key == "governance":
        scene_governance_page()
    elif scene_key == "sector":
        scene_sector_page()
    else:
        if scene_exec_page:
            scene_exec_page()
        else:
            st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_uhn_dashboard()
