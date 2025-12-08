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
from pathlib import Path
from typing import Optional, List, Dict, Callable
from urllib.parse import urlencode
from datetime import datetime

import streamlit as st
from streamlit_extras.stylable_container import stylable_container

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
from llm import ChatLLM, LLMNotConfiguredError

# Scenes are implemented in src_page/*
from src_page.exec import scene_executive as scene_exec_page
from src_page.access import scene_access
from src_page.quality import scene_quality as scene_quality_page
from src_page.finance import scene_finance as scene_finance_page
from src_page.production import scene_production as scene_production_page
from src_page.governance import scene_governance as scene_governance_page
from src_page.sector import scene_sector as scene_sector_page


def _render_llm_error(exc: Exception) -> None:
    """Render a helpful error block with basic diagnostics without leaking secrets."""
    import os
    import traceback
    import streamlit as st

    # Basic error message
    st.error(f"LLM error: {type(exc).__name__}: {exc}")

    # Lightweight diagnostics
    try:
        provider = (st.secrets.get("LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "gemini").lower()  # type: ignore[attr-defined]
    except Exception:
        provider = (os.getenv("LLM_PROVIDER") or "gemini").lower()
    try:
        model = (st.secrets.get("MODEL_ID") or os.getenv("MODEL_ID") or "gemini-2.5-flash")  # type: ignore[attr-defined]
    except Exception:
        model = os.getenv("MODEL_ID") or "gemini-2.5-flash"

    # API key presence (do not print the key)
    try:
        key = (st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))  # type: ignore[attr-defined]
    except Exception:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    key_present = bool(key)

    # SDK availability
    try:
        import google.generativeai as genai  # type: ignore
        sdk_ok = True
        sdk_version = getattr(genai, "__version__", "?")
    except Exception:
        sdk_ok = False
        sdk_version = None

    with st.expander("Diagnostics"):
        st.write(
            {
                "provider": provider,
                "model": model,
                "api_key_configured": key_present,
                "google-generativeai_installed": sdk_ok,
                "google-generativeai_version": sdk_version,
            }
        )
        # Last exception traceback (1-2 lines) to aid debugging
        tb = traceback.format_exc(limit=2)
        st.code(tb or "No traceback available.")


def _inject_styles() -> None:
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


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


def _ensure_chat_state() -> None:
    """Initialize chat state with user context for access control."""
    if "chat_messages" not in st.session_state:
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
    """Render floating MajiBot button at bottom-right."""
    if not _chat_enabled():
        return
    
    icon = "🤖"
    with stylable_container("majibot-fab", css_styles = """
            {
                position: fixed;
                right: 32px;
                bottom: 32px;
                width: 64px;
                height: 64px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                text-decoration: none;
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
                transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
                z-index: 1000;
                cursor: pointer;
                border: none;
            }
            .fab-emoji {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -10%);
                font-size: 64px;
                line-height: 1;
                user-select: none; /* User can't highlight the emoji */
                pointer-events: none; /* Clicks pass THROUGH the emoji to the button */
            }
            button {
                background: transparent !important;
                border: none !important;
                color: black !important;
                box-shadow: none !important;
            }                     
        """):
        st.markdown(f'<div class="fab-emoji">{icon}</div>', unsafe_allow_html=True)
        open_clicked = st.button("", key="majibot-fab-btn", help="Chat with Majibot", use_container_width=True)
    
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
                st.rerun()


def _render_chat_modal_body(input_key_suffix: str = "") -> None:
    """Render the chat UI in the current context (used by modal)."""
    _ensure_chat_state()
    messages: List[Dict[str, str]] = st.session_state["chat_messages"]

    # Custom Header
    st.markdown("""
        <div class="gemini-header">
            <div class="gemini-title">
                <span>✨</span> Assistant
            </div>
            <a class='chat-close-link' href='?'>Close</a>
        </div>
    """, unsafe_allow_html=True)

    # Filter out system message
    display_messages = [m for m in messages if m.get("role") != "system"]
    
    if not display_messages:
        st.markdown(
            "<div style='text-align:center;color:#64748b;margin-top:2rem;'>"
            "<p>👋 Hi! I'm your data assistant.</p>"
            "<p style='font-size:0.9em'>Ask me about NRW, collection efficiency, or specific zones.</p>"
            "</div>", 
            unsafe_allow_html=True
        )

    for msg in display_messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # Map role to streamlit avatar/name
        st_role = "user" if role == "user" else "assistant"
        avatar = None if role == "user" else "✨"
        css_class = "chat-bubble chat-bubble--user" if role == "user" else "chat-bubble chat-bubble--assistant"
        
        with st.chat_message(st_role, avatar=avatar):
            st.markdown(f"<div class='{css_class}'>" + content + "</div>", unsafe_allow_html=True)

    # Handle response generation after rerun
    last_msg = messages[-1] if messages else None
    if last_msg and last_msg.get("role") == "user":
        with st.chat_message("assistant", avatar="✨"):
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
    # Get current user for access control
    user = get_current_user()
    
    # Sync state for country - initialize based on user access
    if "selected_country" not in st.session_state:
        # For non-master users, default to their assigned country
        if user and user.role != UserRole.MASTER_USER and user.assigned_country:
            st.session_state["selected_country"] = user.assigned_country
        else:
            st.session_state["selected_country"] = "All"
    
    current_country = st.session_state["selected_country"]
    
    # Validate country selection against user access (prevents unauthorized access)
    current_country = validate_country_selection(current_country)
    st.session_state["selected_country"] = current_country
    
    # Header Layout
    with st.container():
        # Top Row: Title & Clock
        col_title, col_clock = st.columns([3, 1])
        with col_title:
            # Show access level badge for non-master users
            access_badge = ""
            if user and user.role != UserRole.MASTER_USER:
                access_badge = f"""
                <span style='background: #3b82f620; color: #3b82f6; padding: 4px 12px; 
                             border-radius: 20px; font-size: 0.75rem; font-weight: 600;
                             margin-left: 12px; vertical-align: middle;'>
                    🔒 {user.assigned_country} Only
                </span>
                """
            
            st.markdown(f"""
<h1 style='margin-bottom: 0; font-size: 2.2rem;'>Executive Dashboard{access_badge}</h1>
<p style='color: #64748b; font-size: 1.1em; margin-top: 0.5rem; font-weight: 500;'>Water Utility Performance</p>
""", unsafe_allow_html=True)
        
        with col_clock:
            now = datetime.now()
            st.markdown(f"""
<div style='text-align: right; background: #ffffff; padding: 12px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);'>
    <div style='color: #64748b; font-size: 0.85em; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>{now.strftime('%A, %d %B %Y')}</div>
    <div style='color: #0f172a; font-size: 1.8em; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums;'>{now.strftime('%H:%M')}</div>
    <div style='color: #10b981; font-size: 0.75em; font-weight: 600; margin-top: 4px;'>● Live Data Stream</div>
</div>
""", unsafe_allow_html=True)
            
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        # Controls Row
        with st.container():
            st.markdown("""
                <style>
                    div[data-testid="stHorizontalBlock"] {
                        align-items: center;
                    }
                </style>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns([1.5, 1.5, 2])
            
            with c1:
                st.markdown('<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Region Selection</div>', unsafe_allow_html=True)
                
                # Country Selector - Restricted based on user access level
                allowed_countries = get_allowed_countries()
                
                if user and user.role == UserRole.MASTER_USER:
                    # Master users can select "All" or any specific country
                    countries = ["All"] + allowed_countries
                else:
                    # Non-master users can only see their assigned country
                    countries = allowed_countries
                
                # Ensure current selection is valid
                if current_country not in countries:
                    if countries:
                        current_country = countries[0]
                        st.session_state["selected_country"] = current_country
                
                # Check if country selector should be locked (non-master users)
                is_country_locked = user is not None and user.role != UserRole.MASTER_USER
                
                def on_country_change():
                    """Handle country selection change with access validation."""
                    new_country = st.session_state["header_country_select"]
                    # Validate the selection against user access
                    validated = validate_country_selection(new_country)
                    st.session_state["selected_country"] = validated
                
                if is_country_locked:
                    # Show locked indicator for restricted users
                    st.markdown(f"""
                    <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; 
                                padding: 10px 14px; display: flex; align-items: center; gap: 8px;'>
                        <span style='font-size: 1rem;'>🔒</span>
                        <span style='font-weight: 600; color: #334155;'>{current_country}</span>
                        <span style='font-size: 0.7rem; color: #94a3b8;'>(Assigned Region)</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Master users can select any country
                    st.selectbox(
                        "Country",
                        options=countries,
                        index=countries.index(current_country) if current_country in countries else 0,
                        key="header_country_select",
                        label_visibility="collapsed",
                        on_change=on_country_change
                    )

            with c2:
                st.markdown('<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Time Period</div>', unsafe_allow_html=True)
                if "view_period" not in st.session_state:
                    st.session_state["view_period"] = "Monthly"
                    
                st.radio(
                    "Period",
                    ["YTD", "Quarterly", "Monthly"],
                    horizontal=True,
                    key="view_period",
                    label_visibility="collapsed"
                )

            with c3:
                st.markdown('<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Quick Actions</div>', unsafe_allow_html=True)
                ac1, ac2, ac3 = st.columns(3)
                
                with ac1:
                    # Check if user can export data
                    if check_feature_access("export_data"):
                        st.button("📥 Report", key="btn_report", use_container_width=True, help="Download Executive Report")
                    else:
                        st.button("📥 Report", key="btn_report", use_container_width=True, disabled=True, 
                                  help="Export not available for your role")
                
                with ac2:
                    st.button("📅 Meeting", key="btn_meet", use_container_width=True, help="Schedule Meeting")
                
                with ac3:
                    st.button("🔔 Alerts", key="btn_alert", use_container_width=True, help="Alert Settings")
        
        st.markdown("---")


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


def _render_majibot_popup() -> None:
    """Render MajiBot chat in a modal popup with access control."""
    # Check if user has access to AI assistant feature
    if not check_feature_access("ai_assistant"):
        render_feature_disabled_message("ai_assistant")
        return
    
    _ensure_chat_state()
    messages: List[Dict[str, str]] = st.session_state["chat_messages"]
    
    # Daily Insights Section (without performance score)
    insights_cache = st.session_state.get("exec_insights_cache", {})
    
    if insights_cache:
        anomalies = insights_cache.get("anomalies", [])
        suggested = insights_cache.get("suggested_questions", [])
        
        # Show only anomalies (removed score display)
        st.markdown("**💡 Key Insights**")
        if anomalies:
            for anom in anomalies[:3]:
                severity_color = "#ef4444" if anom["severity"] == "critical" else "#f59e0b"
                icon = "🔴" if anom["severity"] == "critical" else "🟡"
                st.markdown(
                    f"""<div style='background: {severity_color}15; padding: 10px; border-radius: 8px; 
                    margin: 8px 0; border-left: 3px solid {severity_color};'>
                    {icon} <span style='font-size: 13px;'>{anom['message']}</span>
                    </div>""", 
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ All metrics stable", icon="✅")
        
        st.markdown("---")
        
        # Suggested Questions
        if suggested:
            st.markdown("**❓ Suggested Questions**")
            for i, question in enumerate(suggested[:3]):
                if st.button(question, key=f"suggest_popup_{i}", use_container_width=True):
                    max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
                    user_turns = sum(1 for m in messages if m.get("role") == "user")
                    if user_turns < max_turns:
                        messages.append({"role": "user", "content": question})
                        st.rerun()
            st.markdown("---")
    
    # Chat Messages
    display_messages = [m for m in messages if m.get("role") != "system"]
    
    if not display_messages:
        st.markdown(
            "<div style='text-align:left;color:#64748b;padding:2rem 0;'>"
            "<p style='font-size: 16px;'>👋 Hi! I'm MajiBot, your AI analyst.</p>"
            "<p style='font-size: 14px;'>Ask me about NRW, collection efficiency, zones, or any metric.</p>"
            "</div>", 
            unsafe_allow_html=True
        )
    
    for msg in display_messages:
        role = msg.get("role")
        content = msg.get("content")
        
        st_role = "user" if role == "user" else "assistant"
        avatar = "👤" if role == "user" else "🤖"
        css_class = "chat-bubble chat-bubble--user" if role == "user" else "chat-bubble chat-bubble--assistant"
        
        with st.chat_message(st_role, avatar=avatar):
            st.markdown(f"<div class='{css_class}'>" + content + "</div>", unsafe_allow_html=True)
    
    # Handle response generation
    last_msg = messages[-1] if messages else None
    if last_msg and last_msg.get("role") == "user":
        with st.chat_message("assistant", avatar="🤖"):
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
    if prompt := st.chat_input("Ask about your data...", key="majibot_popup_input"):
        max_turns = int(os.getenv("CHAT_MAX_TURNS", "20"))
        user_turns = sum(1 for m in messages if m.get("role") == "user")
        if user_turns >= max_turns:
            st.warning("Chat limit reached for this session.")
            return
            
        messages.append({"role": "user", "content": prompt})
        st.rerun()


def _render_main_layout(scene_runner: Callable[[], None], show_header: bool = True) -> None:
    chat_open = False
    if _chat_enabled():
        chat_param = (_get_query_param("chat") or "").lower()
        if chat_param == "open":
            chat_open = True

    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    if show_header:
        _render_overview_banner()
    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    scene_runner()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Render MajiBot popup in a dialog when open
    if chat_open:
        @st.dialog("MajiBot", width="large")
        def show_majibot():
            _render_majibot_popup()
        
        show_majibot()
        # Still render the FAB behind the dialog, it will be hidden by CSS
        _render_majibot_fab()
    else:
        # Show the floating button when chat is closed
        if _chat_enabled():
            _render_majibot_fab()


def render_uhn_dashboard() -> None:
    """Main dashboard entry point with authentication."""
    st.set_page_config(page_title="Executive Dashboard - Water Utility Performance", page_icon="💧", layout="wide")
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
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
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
