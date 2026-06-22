"""
Water Utility Dashboard - Main Application
==========================================

This is the main entry point for the Water Utility Performance Dashboard.
It includes:
- User authentication and role-based access control
- Data access filtering based on user permissions
- Country and zone restrictions for data privacy compliance

Authentication Flow:
1. User lands on login page if not authenticated
2. After successful login, user sees dashboard filtered to their access level
3. Non-master users can only see data from their assigned country
4. All data queries are filtered through access control checks
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, List, Dict, Callable, Union
from urllib.parse import urlencode
from datetime import datetime
import io
import base64

import streamlit as st
import pandas as pd


def stylable_container(key: str, css_styles: Union[str, List[str]]):
    """Container whose child elements can be styled via scoped CSS.

    Inlined from ``streamlit_extras.stylable_container`` (v0.7.8, MIT,
    Lukas Masuch) so the app no longer depends on the whole
    ``streamlit-extras`` package — which dragged in ~15 transitive
    widget packages (matplotlib, faker, markdownlit, …) just for this one
    helper, bloating the Streamlit Cloud install and occasionally failing
    to resolve. The behaviour here is byte-identical to the original:
    Streamlit assigns ``st-key-<key>`` as a CSS class on the container, and
    we emit a ``<style>`` block scoped to that class.
    """
    class_name = re.sub(r"[^a-zA-Z0-9_-]", "-", key.strip())
    class_name = f"st-key-{class_name}"

    if isinstance(css_styles, str):
        css_styles = [css_styles]

    # Remove unneeded spacing that is added by the html element.
    css_styles = list(css_styles) + [
        """
> div:first-child {
margin-bottom: -1rem;
}
"""
    ]

    style_text = "\n<style>\n"
    for style in css_styles:
        style_text += f"\n.st-key-{class_name} {style}\n"
    style_text += "\n    </style>\n"

    container = st.container(key=class_name)
    container.html(style_text)
    return container

# Import authentication module - provides role-based access control
from auth import (
    init_session_state as init_auth_state,
    is_authenticated,
    get_current_user,
    get_allowed_countries,
    can_access_country,
    validate_country_selection,
    check_feature_access,
    render_login_page,
    render_user_info_sidebar,
    render_access_denied_message,
    render_feature_disabled_message,
    render_admin_settings_page,
    UserRole,
)

from utils import get_zones, prepare_service_data
from llm import ChatLLM, LLMNotConfiguredError, _get_secret

# Scenes are implemented in src_page/*
from src_page.exec import scene_executive as scene_exec_page
from src_page.access import scene_access
from src_page.quality import scene_quality as scene_quality_page
from src_page.finance import scene_finance as scene_finance_page
from src_page.production import scene_production as scene_production_page
from src_page.governance import scene_governance as scene_governance_page
from src_page.sector import scene_sector as scene_sector_page
from src_page.forecasting import scene_forecasting as scene_forecasting_page


def _render_llm_error(exc: Exception) -> None:
    """Render a helpful error block with basic diagnostics without leaking secrets."""
    import os
    import traceback
    import streamlit as st

    # Get error details
    error_msg = str(exc)
    
    # Helper to get secret from top-level or [llm] section
    def _get_secret_value(name: str) -> str | None:
        try:
            # Check top-level
            if hasattr(st.secrets, name):
                return getattr(st.secrets, name)
            # Check under [llm] section
            if hasattr(st.secrets, "llm"):
                llm_sec = st.secrets["llm"]
                if hasattr(llm_sec, name):
                    return getattr(llm_sec, name)
        except Exception:
            pass
        return os.getenv(name)
    
    # Check for common configuration issues
    provider = (_get_secret_value("LLM_PROVIDER") or "gemini").lower()
    
    if provider == "grok":
        key = _get_secret_value("GROK_API_KEY") or _get_secret_value("XAI_API_KEY")
        model = _get_secret_value("MODEL_ID") or "grok-beta"
    elif provider == "glm":
        key = _get_secret_value("GLM_API_KEY") or _get_secret_value("ZHIPU_API_KEY")
        model = _get_secret_value("MODEL_ID") or "glm-4-flash"
    else:
        key = _get_secret_value("GEMINI_API_KEY") or _get_secret_value("GOOGLE_API_KEY")
        model = _get_secret_value("MODEL_ID") or "gemini-1.5-flash"
        
    key_present = bool(key) and "your_api_key_here" not in (key or "") and "your_key_here" not in (key or "")

    # Show user-friendly error message
    if not key_present:
        if key and ("your_api_key_here" in key or "your_key_here" in key):
            st.warning(f"**MajiBot AI Configuration Incomplete**\n\nThe API key is still set to the placeholder value. Please replace it with your actual {provider} API key.")
        elif provider == "grok":
            st.warning("**MajiBot AI is not configured**\n\nTo enable the AI assistant with Grok, please configure your `GROK_API_KEY` in the environment variables or Streamlit secrets.")
        elif provider == "glm":
            st.warning("**MajiBot AI is not configured**\n\nTo enable the AI assistant with GLM, please configure your `GLM_API_KEY` in the environment variables or Streamlit secrets.")
        else:
            st.warning("**MajiBot AI is not configured**\n\nTo enable the AI assistant, please configure your Gemini API key in the environment variables or Streamlit secrets.")
    elif error_msg and ("leaked" in error_msg.lower() or "403" in error_msg):
        st.error("**API key check failed**\n\nThe API key appears to be invalid or revoked. Please check your configuration.")
    elif error_msg and ("API" in error_msg or "key" in error_msg.lower()):
        st.warning(f"**MajiBot AI Configuration Error**\n\nThere was an issue with the API key for {provider}. Please verify it is valid.\n\n**Error Details:** {error_msg}")
    elif error_msg:
        st.error(f"**MajiBot error**: {error_msg[:200]}")

    # Diagnostics in expander (for debugging)
    with st.expander("Diagnostics (for administrators)"):
        
        sdk_status = {}
        if provider in ("grok", "glm"):
            try:
                import openai
                sdk_status["openai_installed"] = True
                sdk_status["openai_version"] = getattr(openai, "__version__", "?")
            except Exception:
                sdk_status["openai_installed"] = False
        else:
            try:
                import google.generativeai as genai
                sdk_status["google-generativeai_installed"] = True
                sdk_status["google-generativeai_version"] = getattr(genai, "__version__", "?")
            except Exception:
                sdk_status["google-generativeai_installed"] = False

        diag_info = {
            "provider": provider,
            "model": model,
            "api_key_configured": key_present,
        }
        diag_info.update(sdk_status)
        st.write(diag_info)
        
        st.markdown("**To fix this:**")
        
        if provider == "grok":
            st.markdown("""
            1. Add to `.env` or `.streamlit/secrets.toml`:
               ```
               LLM_PROVIDER = "grok"
               GROK_API_KEY = "your_key_here"
               ```
            2. Ensure `openai` package is installed:
               ```
               pip install openai
               ```
            """)
        elif provider == "glm":
            st.markdown("""
            1. Add to `.env` or `.streamlit/secrets.toml`:
               ```
               LLM_PROVIDER = "glm"
               GLM_API_KEY = "your_key_here"
               MODEL_ID = "glm-4-flash"
               ```
            2. Ensure `openai` package is installed:
               ```
               pip install openai
               ```
            """)
        else:
            st.markdown("""
            1. Create a `.env` file in the Dashboard folder with:
               ```
               GEMINI_API_KEY=your_api_key_here
               ```
            2. Or set the environment variable before running:
               ```
               export GEMINI_API_KEY=your_api_key_here
               ```
            3. Or add to Streamlit secrets (`.streamlit/secrets.toml`):
               ```
               GEMINI_API_KEY = "your_api_key_here"
               ```
            """)


def _inject_styles() -> None:
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

    # Register the shared Plotly template so every chart in every page
    # inherits the same fonts, colors, and gridlines.
    try:
        from charts import register_adi_template
        register_adi_template()
    except Exception:
        pass


def _chat_enabled() -> bool:
    """Check if chat widget is enabled and user has access."""
    # Check if user has access to AI assistant feature
    if not check_feature_access("ai_assistant"):
        return False
    
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


def _hydrate_api_keys_from_store() -> None:
    """Pull persisted API keys into session_state once per session so the
    LLM client can pick them up without the user opening settings first."""
    if st.session_state.get("_api_keys_hydrated"):
        return
    try:
        from data import keystore
        from llm import KNOWN_BASE_URLS

        # Restore the previously chosen default provider/model first so any LLM
        # call made before the user opens settings uses them.
        default_provider = keystore.get_preference("default_provider")
        if default_provider:
            st.session_state.setdefault("ai_provider", default_provider)
        default_model = keystore.get_preference("default_model")
        if default_model:
            st.session_state.setdefault("ai_model", default_model)

        # Hydrate stored keys + base URLs for every known provider plus the
        # user's default (which may be a custom one).
        providers = set(KNOWN_BASE_URLS) | {"gemini"}
        if default_provider:
            providers.add(default_provider)
        for provider in providers:
            key = keystore.get_api_key(provider)
            if key:
                st.session_state.setdefault(f"ai_api_key_{provider}", key)
            base_url = keystore.get_preference(f"base_url:{provider}")
            if base_url:
                st.session_state.setdefault(f"ai_base_url_{provider}", base_url)
    except Exception:
        pass
    st.session_state["_api_keys_hydrated"] = True


def _ensure_chat_state() -> None:
    """Initialize chat state with user context for access control."""
    _hydrate_api_keys_from_store()
    if "chat_messages" not in st.session_state:
        # Initialize Majibot session state
        st.session_state["majibot_open"] = False
        st.session_state["majibot_status"] = "Closed"
        
        # Include user context in system prompt for personalized responses
        user = get_current_user()
        user_context = ""
        if user:
            user_context = (
                f"\n\nUser Context:\n"
                f"- User: {user.full_name} ({user.role.display_name})\n"
                f"- Access: {'All countries' if user.role == UserRole.MASTER_USER else user.assigned_country}\n"
                f"- Important: Only provide insights about data the user has access to."
            )
        
        st.session_state["chat_messages"] = [
            {
                "role": "system",
                "content": (
                    "You are MajiBot, an AI data analyst for a water utility Managing Director. "
                    "Your role is to provide executive-level insights, not just data. "
                    "When answering:\n"
                    "1. Start with the business impact, then explain the data.\n"
                    "2. Connect insights across datasets (e.g., 'Low service hours correlate with poor collection').\n"
                    "3. Suggest actionable next steps (e.g., 'Consider investigating Zone B's billing system').\n"
                    "4. Use executive language: 'critical', 'opportunity', 'risk', not technical jargon.\n"
                    "5. Reference specific zones, time periods, and metrics from the current dashboard context.\n"
                    "Keep responses concise (2-3 sentences) unless asked for detailed analysis."
                    + user_context
                ),
            }
        ]

        if 'chat_open' not in st.session_state:
            st.session_state['chat_open'] = False

def _set_chat_open_state(open_state: bool) -> None:
    """Toggle chat open state without forcing a page reload."""
    st.session_state["chat_open"] = open_state
    _set_query_param("chat", "open" if open_state else None)

def _render_majibot_fab() -> None:
    """Render floating MajiBot button at bottom-right.

    The FAB CSS lives in styles.css (under `.adi-majibot-fab`) — earlier we
    relied on `stylable_container` to inject inline rules, but that didn't
    always run for the FAB which left it positioned `static` halfway down
    the document. A plain keyed container + a global rule is deterministic
    and centres the icon via flex layout.
    """
    if not _chat_enabled():
        return

    with st.container(key="majibot-fab-host"):
        st.markdown('<span class="adi-majibot-fab__icon">chat_bubble</span>', unsafe_allow_html=True)
        open_clicked = st.button("", key="majibot-fab-btn", help="Chat with MajiBot",
                                 width="stretch")

    if open_clicked:
        _set_chat_open_state(True)
        st.rerun()


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

        # If last message is from the user, stream assistant reply first (keeps input at bottom)
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.get("role") == "user":
            try:
                client = ChatLLM()
                trimmed = ChatLLM.trim_history(messages, max_messages=16)
                placeholder = st.empty()
                acc = ""
                for chunk in client.stream_chat(trimmed):
                    acc += chunk
                    placeholder.markdown(
                        f"<div class='chat-bubble chat-bubble--assistant'>" + acc + "▌</div>",
                        unsafe_allow_html=True,
                    )
                placeholder.markdown(
                    f"<div class='chat-bubble chat-bubble--assistant'>" + acc + "</div>",
                    unsafe_allow_html=True,
                )
                if acc.strip():
                    messages.append({"role": "assistant", "content": acc})
                else:
                    _render_llm_error(RuntimeError("No content returned by model"))
            except Exception as e:
                _render_llm_error(e)

        # Input + actions in a form so we can clear on submit safely (rendered at bottom)
        with st.form("chat_form_sidebar", clear_on_submit=True):
            prompt = st.text_area(
                "Ask a question",
                key="chat_input_text_sidebar",
                height=90,
                placeholder="Ask about metrics, filters, or data…",
            )
            send_clicked = st.form_submit_button("Send", width="stretch")

        if st.button("Close", key="sidebar_close_btn", width="stretch"):
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
                st.rerun()


def _render_chat_modal_body(input_key_suffix: str = "") -> None:
    """Render the chat UI in the current context (used by modal)."""
    _ensure_chat_state()
    messages: List[Dict[str, str]] = st.session_state["chat_messages"]

    # Custom Header
    st.markdown("""
        <div class="gemini-header">
            <div class="gemini-title">
                <span class="icon icon-brand">auto_awesome</span> Assistant
            </div>
            <a class='chat-close-link' href='?'>Close</a>
        </div>
    """, unsafe_allow_html=True)

    # Filter out system message
    display_messages = [m for m in messages if m.get("role") != "system"]
    
    if not display_messages:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state__title">Hi, I\'m your data assistant</div>'
            '<div class="empty-state__description">Ask me about NRW, collection efficiency, or specific zones.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    for msg in display_messages:
        role = msg.get("role")
        content = msg.get("content")

        # Map role to streamlit avatar/name
        st_role = "user" if role == "user" else "assistant"
        css_class = "chat-bubble chat-bubble--user" if role == "user" else "chat-bubble chat-bubble--assistant"

        with st.chat_message(st_role):
            st.markdown(f"<div class='{css_class}'>" + content + "</div>", unsafe_allow_html=True)

    # Handle response generation after rerun
    last_msg = messages[-1] if messages else None
    if last_msg and last_msg.get("role") == "user":
        with st.chat_message("assistant"):
            try:
                client = ChatLLM()
                trimmed = ChatLLM.trim_history(messages, max_messages=16)
                response_placeholder = st.empty()
                full_response = ""
                for chunk in client.stream_chat(trimmed):
                    full_response += chunk
                    response_placeholder.markdown(
                        f"<div class='chat-bubble chat-bubble--assistant'>" + full_response + "▌</div>",
                        unsafe_allow_html=True,
                    )
                response_placeholder.markdown(
                    f"<div class='chat-bubble chat-bubble--assistant'>" + full_response + "</div>",
                    unsafe_allow_html=True,
                )
                if full_response.strip():
                    messages.append({"role": "assistant", "content": full_response})
                else:
                    _render_llm_error(RuntimeError("No content returned by model"))
            except Exception as e:
                _render_llm_error(e)

    # Chat Input (render at bottom)
    if prompt := st.chat_input("Ask a question about your data...", key=f"chat_input{input_key_suffix}"):
        max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
        user_turns = sum(1 for m in messages if m.get("role") == "user")
        if user_turns >= max_turns:
            st.warning("You have reached the chat limit for this session.")
            return
            
        # Add user message
        messages.append({"role": "user", "content": prompt})
        st.rerun()


def _render_overview_banner() -> None:
    """Render the main dashboard header with access-controlled filters."""
    from utils import render_page_header

    user = get_current_user()

    # Sync state for country - initialize based on user access
    if "selected_country" not in st.session_state:
        if user and user.role != UserRole.MASTER_USER and user.assigned_country:
            st.session_state["selected_country"] = user.assigned_country
        else:
            st.session_state["selected_country"] = "All"

    current_country = validate_country_selection(st.session_state["selected_country"])
    st.session_state["selected_country"] = current_country

    # Build access-level badges for non-master users
    badges: List[Dict[str, str]] = []
    if user and user.role != UserRole.MASTER_USER:
        badges.append({"label": f"Region: {user.assigned_country}", "kind": "brand"})

    render_page_header(
        "Executive Dashboard",
        eyebrow="Water Utility Performance",
        subtitle="Real-time view of access, service quality, finance and production.",
        icon="dashboard",
        badges=badges,
        show_clock=True,
    )

    # Filter controls — sit in a flat horizontal strip
    with st.container():
        c1, c2, c3 = st.columns([1.5, 1.5, 1])

        with c1:
            st.markdown('<div class="text-eyebrow">Region</div>', unsafe_allow_html=True)

            allowed_countries = get_allowed_countries()
            if user and user.role == UserRole.MASTER_USER:
                countries = ["All"] + allowed_countries
            else:
                countries = allowed_countries

            if current_country not in countries and countries:
                current_country = countries[0]
                st.session_state["selected_country"] = current_country

            if "header_country_select" not in st.session_state:
                st.session_state["header_country_select"] = current_country

            is_country_locked = user is not None and user.role != UserRole.MASTER_USER

            def on_country_change():
                new_country = st.session_state.get("header_country_select", current_country)
                validated = validate_country_selection(new_country)
                st.session_state["selected_country"] = validated
                st.session_state["header_country_select"] = validated

            if is_country_locked:
                st.markdown(
                    '<div class="locked-indicator">'
                    '<span class="icon icon-sm icon-muted">lock</span>'
                    f'<span>{current_country}</span>'
                    '<span class="locked-indicator__hint">Assigned region</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.selectbox(
                    "Country",
                    options=countries,
                    key="header_country_select",
                    label_visibility="collapsed",
                    on_change=on_country_change,
                )

        with c2:
            st.markdown('<div class="text-eyebrow">Time period</div>', unsafe_allow_html=True)
            if "view_period" not in st.session_state:
                st.session_state["view_period"] = "Monthly"

            st.radio(
                "Period",
                ["Quarterly", "Monthly"],
                horizontal=True,
                key="view_period",
                label_visibility="collapsed",
            )

        with c3:
            st.markdown('<div class="text-eyebrow">Year</div>', unsafe_allow_html=True)
            available_years = sorted([2020, 2021, 2022, 2023, 2024], reverse=True)
            if "selected_year" not in st.session_state:
                st.session_state["selected_year"] = available_years[0]
            current_year = st.session_state.get("selected_year", available_years[0])
            if current_year not in available_years:
                current_year = available_years[0]
                st.session_state["selected_year"] = current_year

            selected_year = st.selectbox(
                "Year",
                options=available_years,
                index=available_years.index(current_year),
                key="header_year_select",
                label_visibility="collapsed",
            )
            st.session_state["selected_year"] = selected_year

        st.markdown("<hr/>", unsafe_allow_html=True)


def _sidebar_filters() -> None:
    st.sidebar.title("Filters")
    
    # Get current user for access control
    from auth import get_current_user, UserRole
    user = get_current_user()
    
    # Load data for filters (using service data as it has the most granular time/location info)
    service_data = prepare_service_data()
    df_service = service_data["full_data"]
    
    # 1. Country - Access controlled
    if user and user.role == UserRole.MASTER_USER:
        # Master users can select "All" or any specific country
        countries = ['All'] + service_data["countries"]
    elif user and user.assigned_country:
        # Non-master users only see their assigned country
        countries = [user.assigned_country]
    else:
        countries = ['All'] + service_data["countries"]
    
    # Initialize session state if not present
    if "selected_country" not in st.session_state:
        if user and user.role == UserRole.MASTER_USER:
            st.session_state["selected_country"] = "All"
        elif user and user.assigned_country:
            st.session_state["selected_country"] = user.assigned_country
        else:
            st.session_state["selected_country"] = "All"
    
    # Ensure current selection is valid for this user
    current_country = st.session_state["selected_country"]
    if current_country not in countries:
        current_country = countries[0] if countries else "All"
        st.session_state["selected_country"] = current_country
    
    # For non-master users, show locked indicator instead of dropdown
    if user and user.role != UserRole.MASTER_USER:
        st.sidebar.markdown(f"**Country:** {user.assigned_country}")
    else:
        selected_country = st.sidebar.selectbox('Country', countries, key='selected_country')

    # 2. Zone
    selected_country = st.session_state.get("selected_country", "All")
    if selected_country != 'All':
        # Case-insensitive zone lookup
        zones = ['All'] + sorted(df_service[df_service['country'].str.lower() == selected_country.lower()]['zone'].unique().tolist())
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

    # Reset button - respects user access
    if st.sidebar.button("Reset filters"):
        if user and user.role == UserRole.MASTER_USER:
            st.session_state["selected_country"] = "All"
        elif user and user.assigned_country:
            st.session_state["selected_country"] = user.assigned_country
        else:
            st.session_state["selected_country"] = "All"
        st.session_state["selected_zone"] = "All"
        if available_years:
            st.session_state["selected_year"] = available_years[0]
        st.session_state["selected_month"] = "All"
        st.rerun()

    # AI Model Settings — same editable, scalable form used in the chat panel.
    if check_feature_access("ai_assistant"):
        st.sidebar.markdown("---")
        with st.sidebar.expander("AI settings", expanded=False):
            _render_llm_provider_form(scope="sidebar")


def _render_indicator_search() -> Optional[str]:
    """
    Render indicator search box and results.
    Returns selected question if user clicks a search result.
    """
    from ai_insights import search_indicators, get_search_suggestions
    
    st.markdown(
        '<div class="text-eyebrow" style="margin-bottom: 8px;">'
        '<span class="icon icon-sm icon-muted">search</span>&nbsp;Find an indicator'
        '</div>',
        unsafe_allow_html=True,
    )

    # Search input
    search_query = st.text_input(
        "Search for a metric or indicator...",
        placeholder="e.g., NRW, collection efficiency, water quality",
        key="indicator_search_input",
        label_visibility="collapsed"
    )

    # Show search results
    if search_query and len(search_query) >= 2:
        results = search_indicators(search_query, max_results=4)

        if results:
            for result in results:
                if result["domain"] == "Water Supply":
                    domain_icon_html = '<span class="icon icon-sm" style="color: var(--data-water);">water_drop</span>'
                elif result["domain"] == "Sanitation":
                    domain_icon_html = '<span class="icon icon-sm" style="color: var(--data-sanitation);">shower</span>'
                else:
                    domain_icon_html = '<span class="icon icon-sm icon-muted">category</span>'
                st.markdown(
                    '<div class="indicator-result">'
                    f'<div class="indicator-result__title">{domain_icon_html} {result["indicator"].title()}</div>'
                    '<div class="indicator-result__meta">'
                    '<span class="icon icon-sm icon-muted">help_outline</span>'
                    f' {result["guidance"]} '
                    f'<span class="badge">{result["frequency"]}</span>'
                    '</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="text-caption">No matching indicators found. Try different keywords.</div>', unsafe_allow_html=True)
    else:
        suggestions = get_search_suggestions()[:8]
        st.markdown(f'<div class="text-caption">Quick: {", ".join(suggestions)}</div>', unsafe_allow_html=True)

    st.markdown("<hr/>", unsafe_allow_html=True)
    return None


# Free-text suggestions only — the model field is editable, not a fixed list.
_MODEL_SUGGESTIONS = {
    "gemini": "gemini-2.5-flash, gemini-2.5-pro, gemini-1.5-flash",
    "grok": "grok-4-fast, grok-3, grok-3-mini",
    "glm": "glm-4-flash, glm-4-air, glm-4",
    "openai": "gpt-4o-mini, gpt-4o, o4-mini",
    "deepseek": "deepseek-chat, deepseek-reasoner",
    "openrouter": "openai/gpt-4o-mini, anthropic/claude-3.5-sonnet",
    "mistral": "mistral-small-latest, mistral-large-latest",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
}


def _render_llm_provider_form(scope: str = "panel") -> None:
    """Editable, provider-agnostic MajiBot configuration.

    Provider, model and base URL are free-text inputs (not fixed dropdowns),
    so any OpenAI-compatible service can be wired up at runtime — type the
    provider name, paste its base URL and key, and pick a model. Known
    providers (gemini, grok, glm, openai, deepseek, openrouter, ...) auto-fill
    their base URL. Everything is persisted via `data.keystore` so it survives
    future sessions.

    `scope` namespaces the widget keys so the sidebar and chat-panel copies of
    this form don't collide in Streamlit's session state.
    """
    from data import keystore
    from llm import KNOWN_BASE_URLS

    persists = keystore.persistence_enabled()

    if scope == "panel":
        st.markdown(
            '<div class="majibot-section-title">'
            '<span class="icon icon-sm icon-muted">tune</span>'
            '<span>Model settings</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    current_provider = (
        st.session_state.get("ai_provider")
        or keystore.get_preference("default_provider")
        or "gemini"
    ).lower()

    provider = st.text_input(
        "Provider",
        value=current_provider,
        key=f"majibot_provider_input_{scope}",
        help="e.g. gemini, openai, grok, glm, deepseek, openrouter — or any OpenAI-compatible service.",
        placeholder="gemini",
    ).strip().lower() or "gemini"

    is_gemini = provider == "gemini"

    # Base URL — OpenAI-compatible providers only; auto-filled for known ones.
    base_url = ""
    if not is_gemini:
        default_base = (
            st.session_state.get(f"ai_base_url_{provider}")
            or keystore.get_preference(f"base_url:{provider}")
            or KNOWN_BASE_URLS.get(provider, "")
        )
        base_url = st.text_input(
            "Base URL",
            value=default_base,
            key=f"majibot_base_url_input_{scope}_{provider}",
            help="OpenAI-compatible endpoint. Auto-filled for known providers; required for custom ones.",
            placeholder="https://api.example.com/v1",
        ).strip()

    # Model — free text, with a helpful default/suggestion for known providers.
    default_model = ""
    if st.session_state.get("ai_provider") == provider:
        default_model = st.session_state.get("ai_model") or ""
    if not default_model and keystore.get_preference("default_provider") == provider:
        default_model = keystore.get_preference("default_model") or ""
    if not default_model and provider in _MODEL_SUGGESTIONS:
        default_model = _MODEL_SUGGESTIONS[provider].split(",")[0].strip()
    model = st.text_input(
        "Model",
        value=default_model,
        key=f"majibot_model_input_{scope}_{provider}",
        placeholder="model name",
        help=("Suggestions: " + _MODEL_SUGGESTIONS[provider])
        if provider in _MODEL_SUGGESTIONS
        else "Any model name your provider supports.",
    ).strip()

    # Auto-persist provider / model / base URL as defaults for next session.
    st.session_state["ai_provider"] = provider
    if keystore.get_preference("default_provider") != provider:
        keystore.set_preference("default_provider", provider)
    if model:
        st.session_state["ai_model"] = model
        if keystore.get_preference("default_model") != model:
            keystore.set_preference("default_model", model)
    if not is_gemini and base_url:
        st.session_state[f"ai_base_url_{provider}"] = base_url
        if keystore.get_preference(f"base_url:{provider}") != base_url:
            keystore.set_preference(f"base_url:{provider}", base_url)

    if persists:
        st.caption("Provider, model and base URL auto-save for future sessions.")
    else:
        st.caption(
            "On this deployment your key and settings are used for this session "
            "only — nothing is stored on the server or shared with other visitors."
        )

    # ---- API key: masked "Stored" view with Edit/Clear, or an edit field. ----
    key_label = f"{provider.upper()}_API_KEY"
    key_state = f"ai_api_key_{provider}"
    edit_flag = f"majibot_key_edit_{scope}_{provider}"

    stored_key = keystore.get_api_key(provider) or ""
    if stored_key and not st.session_state.get(key_state):
        st.session_state[key_state] = stored_key

    has_stored = bool(st.session_state.get(key_state))
    in_edit_mode = st.session_state.get(edit_flag, False) or not has_stored

    if has_stored and not in_edit_mode:
        val = st.session_state[key_state]
        masked = "•" * 4 + (val[-4:] if len(val) > 4 else "••••")
        st.markdown(
            f'<div class="majibot-key-stored">'
            f'<div class="majibot-key-stored__label">{key_label}</div>'
            f'<div class="majibot-key-stored__value">'
            f'<span class="icon icon-sm" style="color: var(--success);">lock</span>'
            f'<code>{masked}</code>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        edit_col, clear_col = st.columns(2)
        with edit_col:
            if st.button("Edit", key=f"majibot_key_edit_btn_{scope}_{provider}", width="stretch"):
                st.session_state[edit_flag] = True
                st.rerun()
        with clear_col:
            if st.button("Clear", key=f"majibot_key_clear_btn_{scope}_{provider}", width="stretch"):
                keystore.clear_api_key(provider)
                st.session_state[key_state] = ""
                st.session_state[edit_flag] = True
                st.rerun()
    else:
        widget_key = f"majibot_key_input_{scope}_{provider}"
        st.text_input(
            key_label,
            value=st.session_state.get(key_state, ""),
            type="password",
            key=widget_key,
            help=(
                "Remembered on this machine at ~/.adi_water_dashboard/keys.json (chmod 0600)."
                if persists
                else "Used for this session only — not stored on the server, not shared with other visitors."
            ),
            placeholder=f"Paste your {key_label}",
        )
        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("Save key", key=f"majibot_key_save_btn_{scope}_{provider}",
                         icon=":material/save:", type="primary", width="stretch"):
                value = st.session_state.get(widget_key, "").strip()
                if value:
                    keystore.set_api_key(provider, value)
                    st.session_state[key_state] = value
                    st.session_state[edit_flag] = False
                    st.toast("API key saved", icon=":material/check_circle:")
                    st.rerun()
                else:
                    st.warning("Enter a key first.")
        with cancel_col:
            if has_stored:
                if st.button("Cancel", key=f"majibot_key_cancel_btn_{scope}_{provider}", width="stretch"):
                    st.session_state[edit_flag] = False
                    st.rerun()


def _render_majibot_settings() -> None:
    """Provider / model / API-key configuration shown inside the chat panel."""
    _render_llm_provider_form(scope="panel")


def _majibot_panel_css() -> str:
    """Floating panel CSS. All rules nested inside the wrapper selector
    so nothing leaks (see earlier stylable_container CSS-leak fix)."""
    return """
            {
                position: fixed !important;
                right: 40px;
                bottom: 40px;
                width: min(440px, calc(100vw - 80px));
                height: min(740px, calc(100vh - 120px));
                background: var(--surface, #ffffff);
                border: 1px solid var(--border, #e4e9f1);
                border-radius: 16px;
                box-shadow: 0 24px 48px rgba(15, 23, 42, 0.18),
                            0 4px 12px rgba(15, 23, 42, 0.06);
                z-index: 1000;
                overflow: hidden;
                display: flex !important;
                flex-direction: column;

                /* Tighten Streamlit's default padding around every direct
                   child element-container. Real horizontal padding comes
                   from the panel wrapper's own padding. */
                padding: 12px 16px 12px;

                /* The dedicated scroll region — only this container grows
                   and scrolls. `min-height: 0` lets it shrink inside the
                   flex column so the form below stays anchored to the
                   bottom.

                   Why the explicit max-height: in the actual DOM each
                   direct child of the panel is a `stLayoutWrapper` with
                   `flex: 0 1 auto`, which sizes to its content rather
                   than filling the panel — so the inner messages block's
                   `flex: 1 1 auto` had no constraint to play against and
                   the chat region just grew with the conversation,
                   pushing the form off-screen with no scrollbar. Capping
                   at panel-height − (header ~72px + form ~80px + chrome)
                   forces the overflow so content actually becomes
                   scrollable. */
                .st-key-majibot-messages-scroll {
                    flex: 1 1 auto !important;
                    min-height: 0 !important;
                    max-height: calc(min(740px, 100vh - 120px) - 180px) !important;
                    overflow-y: auto !important;
                    overscroll-behavior: contain;
                    scrollbar-width: thin;
                    padding-right: 4px;
                }
                .st-key-majibot-messages-scroll::-webkit-scrollbar { width: 8px; }
                .st-key-majibot-messages-scroll::-webkit-scrollbar-thumb {
                    background: var(--border);
                    border-radius: 4px;
                }
                .st-key-majibot-messages-scroll::-webkit-scrollbar-thumb:hover {
                    background: var(--text-tertiary);
                }

                /* Streamlit wraps every element in a stElementContainer with
                   default vertical padding/margin. Collapse those when they
                   wrap our dividers and tighten everywhere else. */
                [data-testid="stElementContainer"]:has(.majibot-divider) {
                    margin: 0 !important;
                    padding: 0 !important;
                    height: auto !important;
                    min-height: 0 !important;
                }
                [data-testid="stVerticalBlock"] {
                    gap: 8px !important;
                }
                [data-testid="stElementContainer"] {
                    margin: 0 !important;
                }

                /* The header is the first stLayoutWrapper inside the
                   panel. Pin it to the top with a subtle bottom divider —
                   the rest of the content sits in its own scroll region. */
                > [data-testid="stLayoutWrapper"]:first-child {
                    flex: 0 0 auto;
                    padding-bottom: 8px;
                    margin-bottom: 4px;
                    border-bottom: 1px solid var(--divider);
                }

                /* Header icon-buttons: square, ghost. Scoped to the first
                   layout wrapper only (the header row). */
                > [data-testid="stLayoutWrapper"]:first-child
                    [data-testid="stButton"] button {
                    background: transparent;
                    border: 1px solid transparent;
                    color: var(--text-secondary);
                    padding: 4px;
                    min-height: 32px;
                    height: 32px;
                    width: 32px;
                }
                > [data-testid="stLayoutWrapper"]:first-child
                    [data-testid="stButton"] button:hover {
                    background: var(--surface-muted);
                    border-color: var(--border);
                    color: var(--text-primary);
                }

                /* Suggested-question buttons: spacing + soft chrome. */
                [data-testid="stButton"]:has(button[kind="secondary"]) {
                    margin: 4px 0 !important;
                }
                [data-testid="stButton"] button[kind="secondary"] {
                    background: var(--surface-muted);
                    border: 1px solid var(--border);
                    color: var(--text-primary);
                    text-align: left;
                    justify-content: flex-start;
                    font-weight: 500;
                    padding: 8px 12px;
                    white-space: normal;
                    line-height: 1.35;
                }
                [data-testid="stButton"] button[kind="secondary"]:hover {
                    border-color: var(--brand);
                    color: var(--brand-strong);
                }

                /* Form sits at the bottom with proper breathing room.
                   The form's *containing* stLayoutWrapper is the one that
                   needs margin-top: auto since the wrapper is the direct
                   flex child of the panel, not stForm. */
                > [data-testid="stLayoutWrapper"]:last-child {
                    margin-top: auto;
                    padding-top: 8px;
                    border-top: 1px solid var(--divider);
                }
                [data-testid="stForm"] {
                    padding-top: 0 !important;
                    border: none !important;
                    background: transparent !important;
                }

                /* Buttons inside columns (the settings drawer's Edit/Clear,
                   Save/Cancel rows) must not wrap their labels — the narrow
                   panel column was forcing one letter per line. */
                [data-testid="stHorizontalBlock"] [data-testid="stButton"] button,
                [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"],
                [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-primary"] {
                    white-space: nowrap !important;
                    min-width: 0 !important;
                    padding: 6px 10px !important;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                [data-testid="stHorizontalBlock"] [data-testid="stButton"] button p {
                    white-space: nowrap !important;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }

                /* Below ~640px viewport width Streamlit stacks columns,
                   which is wrong for our 440px floating panel: the
                   Edit/Clear buttons end up full-width on separate rows.
                   Force columns side-by-side inside the panel. The
                   header columns use weighted flex-basis (1, 0.22, 0.22)
                   which Streamlit applies inline — they keep their ratio
                   even with row layout. */
                [data-testid="stHorizontalBlock"] {
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    gap: 8px !important;
                }
                [data-testid="stHorizontalBlock"] [data-testid="stColumn"] {
                    width: auto !important;
                    min-width: 0 !important;
                }
            }
        """


def _render_majibot_panel() -> None:
    """Render MajiBot as a bottom-right floating chat panel."""
    if not check_feature_access("ai_assistant"):
        with stylable_container("majibot-panel", css_styles=_majibot_panel_css()):
            render_feature_disabled_message("ai_assistant")
            if st.button("Close", key="majibot_panel_close_denied", width="stretch"):
                _set_chat_open_state(False)
                st.rerun()
        return

    _ensure_chat_state()
    messages: List[Dict[str, str]] = st.session_state["chat_messages"]
    settings_open = st.session_state.get("majibot_settings_open", False)

    with stylable_container("majibot-panel", css_styles=_majibot_panel_css()):
        # Header row — title + subtitle on the left, settings + close on the
        # right. Layout inspired by mature support-chat UIs (Intercom, etc.):
        # two-line header with a stronger product identity.
        hcol1, hcol2, hcol3 = st.columns([1, 0.22, 0.22], vertical_alignment="center")
        with hcol1:
            st.markdown(
                '<div class="majibot-panel__title">'
                '<span class="majibot-panel__avatar"><span class="icon icon-brand">auto_awesome</span></span>'
                '<div class="majibot-panel__name">'
                '<div class="majibot-panel__name-main">MajiBot</div>'
                '<div class="majibot-panel__name-sub">Your data assistant</div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with hcol2:
            if st.button("", key="majibot_panel_settings_btn", icon=":material/tune:",
                         help="Model & API settings"):
                st.session_state["majibot_settings_open"] = not settings_open
                st.rerun()
        with hcol3:
            if st.button("", key="majibot_panel_close_btn", icon=":material/close:",
                         help="Close"):
                _set_chat_open_state(False)
                st.rerun()

        # Settings panel (collapsible). No explicit divider — the sticky
        # header has its own visual separation and an extra <hr> just
        # wastes vertical space inside the panel.
        if settings_open:
            _render_majibot_settings()
            if st.button("Back to chat", key="majibot_settings_done_btn",
                         icon=":material/arrow_back:", type="primary", width="stretch"):
                st.session_state["majibot_settings_open"] = False
                st.rerun()

        # Suggested questions seed
        insights_cache = st.session_state.get("exec_insights_cache", {})
        suggested = insights_cache.get("suggested_questions", [
            "What is the current NRW rate?",
            "How is collection efficiency trending?",
            "Which zones need attention?",
        ])

        # Chat messages — wrapped in a dedicated scroll container so only
        # this region overflows; header stays pinned, form stays anchored.
        # When the settings drawer is open, suppress the chat surface so it
        # doesn't bleed below the model controls.
        display_messages = [m for m in messages if m.get("role") != "system"]
        msg_container = st.container(key="majibot-messages-scroll")
        show_chat_surface = not settings_open
        if show_chat_surface and not display_messages:
            # Greet the signed-in user by first name when available
            current = get_current_user()
            first_name = ""
            if current is not None:
                full = getattr(current, "full_name", None) or getattr(current, "username", "")
                first_name = full.split()[0] if full else ""
            greeting = f"Hi {first_name} \U0001F44B" if first_name else "Hi there \U0001F44B"
            msg_container.markdown(
                '<div class="majibot-empty">'
                f'<div class="majibot-empty__hero">{greeting}<br/>How can I help today?</div>'
                '<div class="majibot-empty__body">'
                'Ask about NRW, collection efficiency, specific zones, or any metric on the dashboard.'
                '</div></div>',
                unsafe_allow_html=True,
            )

        if show_chat_surface:
            with msg_container:
                for msg in display_messages:
                    role = msg.get("role")
                    content = msg.get("content")
                    st_role = "user" if role == "user" else "assistant"
                    css_class = "chat-bubble chat-bubble--user" if role == "user" else "chat-bubble chat-bubble--assistant"
                    with st.chat_message(st_role):
                        st.markdown(f"<div class='{css_class}'>" + content + "</div>", unsafe_allow_html=True)

        # Generate response for the last user message — inside the same
        # scroll container so streamed bubbles share the same overflow region.
        last_msg = messages[-1] if messages else None
        if show_chat_surface and last_msg and last_msg.get("role") == "user":
            user_query = last_msg.get("content", "")
            with msg_container, st.chat_message("assistant"):
                try:
                    from ai_insights import parse_data_query, execute_data_query
                    from utils import load_billing_data, load_production_data

                    parsed_query = parse_data_query(user_query)
                    if parsed_query:
                        billing_df = load_billing_data()
                        prod_df = load_production_data()
                        fin_df = pd.DataFrame()
                        response = execute_data_query(parsed_query, billing_df, prod_df, fin_df)
                        st.markdown(
                            f"<div class='chat-bubble chat-bubble--assistant'>" + response + "</div>",
                            unsafe_allow_html=True,
                        )
                        messages.append({"role": "assistant", "content": response})
                    else:
                        sql_response = None
                        try:
                            client = ChatLLM()
                            sql = client.generate_sql(user_query)
                            if sql:
                                from data.database import query as db_query
                                result_df = db_query(sql)
                                if not result_df.empty:
                                    sql_response = "**Query results** (via text-to-SQL):\n\n"
                                    sql_response += result_df.head(20).to_markdown(index=False)
                                    sql_response += f"\n\n*{len(result_df)} row(s) returned*"
                        except Exception:
                            pass

                        if sql_response:
                            st.markdown(
                                f"<div class='chat-bubble chat-bubble--assistant'>" + sql_response + "</div>",
                                unsafe_allow_html=True,
                            )
                            messages.append({"role": "assistant", "content": sql_response})
                        else:
                            raise ValueError("Query not matched - fall back to LLM")
                except Exception:
                    try:
                        client = ChatLLM()
                        trimmed = ChatLLM.trim_history(messages, max_messages=16)
                        placeholder = st.empty()
                        full_response = ""
                        for chunk in client.stream_chat(trimmed):
                            full_response += chunk
                            placeholder.markdown(
                                f"<div class='chat-bubble chat-bubble--assistant'>" + full_response + "\u258c</div>",
                                unsafe_allow_html=True,
                            )
                        placeholder.markdown(
                            f"<div class='chat-bubble chat-bubble--assistant'>" + full_response + "</div>",
                            unsafe_allow_html=True,
                        )
                        if full_response.strip():
                            messages.append({"role": "assistant", "content": full_response})
                        else:
                            _render_llm_error(RuntimeError("No content returned by model"))
                    except Exception as e:
                        _render_llm_error(e)

        # Suggested questions (above the input, inside the scroll region).
        if show_chat_surface and suggested and not display_messages:
            with msg_container:
                st.markdown(
                    '<div class="text-eyebrow" style="margin-top: 8px;">'
                    '<span class="icon icon-sm icon-muted">lightbulb</span>&nbsp;Try asking'
                    '</div>',
                    unsafe_allow_html=True,
                )
                for i, question in enumerate(suggested[:3]):
                    display_q = question[:60] + "\u2026" if len(question) > 60 else question
                    if st.button(display_q, key=f"majibot_suggest_{i}", width="stretch"):
                        max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
                        user_turns = sum(1 for m in messages if m.get("role") == "user")
                        if user_turns < max_turns:
                            messages.append({"role": "user", "content": question})
                            st.rerun()

        # Input form (Enter-to-send via st.form). Form has its own top
        # border via the panel CSS, so no explicit <hr> needed.
        with st.form("majibot_form", clear_on_submit=True, border=False):
            input_col, send_col = st.columns([1, 0.2], vertical_alignment="bottom")
            with input_col:
                prompt = st.text_input(
                    "Message MajiBot",
                    placeholder="Ask about your data...",
                    key="majibot_panel_input",
                    label_visibility="collapsed",
                )
            with send_col:
                submitted = st.form_submit_button("", icon=":material/send:", type="primary", use_container_width=True)
            if submitted and prompt and prompt.strip():
                max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
                user_turns = sum(1 for m in messages if m.get("role") == "user")
                if user_turns >= max_turns:
                    st.warning("Chat limit reached for this session.")
                else:
                    messages.append({"role": "user", "content": prompt.strip()})
                    st.rerun()

        # Auto-scroll the messages region to the bottom after every rerun.
        # Streamlit reruns the panel on each user/assistant turn; without
        # this, the scroll position stays pinned at the top and new
        # responses appear below the fold. We re-run the scroll on the
        # next frame so any tail markdown has finished laying out.
        if show_chat_surface and display_messages:
            st.markdown(
                """
                <script>
                (function() {
                    const root = window.parent.document;
                    const el = root.querySelector('.st-key-majibot-messages-scroll');
                    if (!el) return;
                    const stick = () => { el.scrollTop = el.scrollHeight; };
                    stick();
                    requestAnimationFrame(stick);
                    setTimeout(stick, 120);
                })();
                </script>
                """,
                unsafe_allow_html=True,
            )


def _render_main_layout(scene_runner: Callable[[], None], show_header: bool = True) -> None:
    chat_open = False
    if _chat_enabled():
        chat_param = (_get_query_param("chat") or "").lower()
        if chat_param == "open":
            chat_open = True
    
    # Update Majibot session state based on chat_open status
    if "majibot_open" not in st.session_state:
        st.session_state["majibot_open"] = chat_open
        st.session_state["majibot_status"] = "Active" if chat_open else "Closed"
    else:
        st.session_state["majibot_open"] = chat_open
        st.session_state["majibot_status"] = "Active" if chat_open else "Closed"

    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    if show_header:
        _render_overview_banner()
    
    # Run the main scene content
    scene_runner()

    # Bottom-right floating widget: FAB always (when enabled),
    # plus the chat panel when open. Both live in fixed-position
    # stylable_containers so the rest of the page stays interactive.
    if _chat_enabled():
        if chat_open:
            _render_majibot_panel()
        else:
            _render_majibot_fab()


def render_uhn_dashboard() -> None:
    """Main dashboard entry point with authentication."""
    st.set_page_config(page_title="Executive Dashboard - Water Utility Performance", page_icon=":material/dashboard:", layout="wide")
    _inject_styles()
    
    # Initialize authentication state
    init_auth_state()
    
    # Check if user is authenticated
    if not is_authenticated():
        # Show login page
        render_login_page()
        return
    
    # User is authenticated - render user info in sidebar
    render_user_info_sidebar()

    def run_scene():
        if scene_exec_page:
            scene_exec_page()
        else:
            st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")

    _render_main_layout(run_scene)


def render_scene_page(scene_key: str) -> None:
    """Render a specific scene page with authentication and access control."""
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon=":material/dashboard:", layout="wide")
    _inject_styles()
    
    # Initialize authentication state
    init_auth_state()
    
    # Check if user is authenticated
    if not is_authenticated():
        # Show login page
        render_login_page()
        return
    
    # User is authenticated - render user info in sidebar
    render_user_info_sidebar()
    # Hydrate persisted provider/model/API-key prefs so LLM calls outside
    # the chat panel still use the user's chosen defaults.
    _hydrate_api_keys_from_store()

    def run_scene():
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
        elif scene_key == "forecasting":
            scene_forecasting_page()
        elif scene_key == "admin":
            # Admin settings page - access controlled within render_admin_settings_page
            render_admin_settings_page()
        else:
            if scene_exec_page:
                scene_exec_page()
            else:
                st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")

    # Admin page doesn't need the overview header
    show_header = scene_key == "exec"
    _render_main_layout(run_scene, show_header=show_header)


if __name__ == "__main__":
    render_uhn_dashboard()
