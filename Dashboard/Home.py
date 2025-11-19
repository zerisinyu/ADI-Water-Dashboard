from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlencode

import streamlit as st

from utils import get_zones
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
            col_send, col_close = st.columns(2)
            send_clicked = col_send.form_submit_button("Send", use_container_width=True)
            close_clicked = col_close.form_submit_button("Close", use_container_width=True)
        if close_clicked:
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
        col_send, col_close = st.columns(2)
        send_clicked = col_send.form_submit_button("Send", use_container_width=True, key=f"send_btn{input_key_suffix}")
        close_clicked = col_close.form_submit_button("Close", use_container_width=True, key=f"close_btn{input_key_suffix}")
    if close_clicked:
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
    if isinstance(zone, dict):
        zone_label = zone.get("name") or "All zones"
    else:
        zone_label = zone or "All zones"
    start = st.session_state.get("start_month") or "Any"
    end = st.session_state.get("end_month") or "Now"

    st.title("Water Utility Performance Dashboard")
    st.caption(f"Latest performance overview for {zone_label} (Months: {start} – {end})")


def _sidebar_filters() -> None:
    st.sidebar.title("Filters")
    zones = get_zones()
    zone_names = ["All"] + [z.get("name") for z in zones]
    sel_zone = st.sidebar.selectbox("Zone", zone_names, index=0, key="global_zone")
    if sel_zone == "All":
        st.session_state["selected_zone"] = None
    else:
        st.session_state["selected_zone"] = next((z for z in zones if z.get("name") == sel_zone), None)

    st.sidebar.markdown("Month range (YYYY-MM)")
    st.sidebar.text_input("Start", value=st.session_state.get("start_month", ""), key="start_month")
    st.sidebar.text_input("End", value=st.session_state.get("end_month", ""), key="end_month")

    st.sidebar.radio("Blockages rate basis", ["per 100 km", "per 1000 connections"], index=0, key="blockage_basis")
    if st.sidebar.button("Reset filters"):
        for k in ["global_zone", "selected_zone", "start_month", "end_month", "blockage_basis"]:
            if k in st.session_state:
                del st.session_state[k]
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
