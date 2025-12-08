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
import io
import base64

import streamlit as st
import pandas as pd
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

    # Get error details
    error_msg = str(exc)
    
    # Check for common configuration issues
    try:
        provider = (st.secrets.get("LLM_PROVIDER") or os.getenv("LLM_PROVIDER") or "gemini").lower()
    except Exception:
        provider = (os.getenv("LLM_PROVIDER") or "gemini").lower()
    
    try:
        key = (st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    except Exception:
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    key_present = bool(key)

    # Show user-friendly error message
    if not key_present:
        st.warning("⚠️ **MajiBot AI is not configured**\n\nTo enable the AI assistant, please configure your Gemini API key in the environment variables or Streamlit secrets.")
    elif "API" in error_msg or "key" in error_msg.lower():
        st.warning("⚠️ **MajiBot AI Configuration Error**\n\nThere was an issue with the API key. Please verify your Gemini API key is valid.")
    else:
        st.error(f"⚠️ **MajiBot Error**: {error_msg[:200]}")

    # Diagnostics in expander (for debugging)
    with st.expander("🔧 Diagnostics (for administrators)"):
        try:
            model = (st.secrets.get("MODEL_ID") or os.getenv("MODEL_ID") or "gemini-2.5-flash")
        except Exception:
            model = os.getenv("MODEL_ID") or "gemini-2.5-flash"
        
        try:
            import google.generativeai as genai
            sdk_ok = True
            sdk_version = getattr(genai, "__version__", "?")
        except Exception:
            sdk_ok = False
            sdk_version = None

        st.write({
            "provider": provider,
            "model": model,
            "api_key_configured": key_present,
            "google-generativeai_installed": sdk_ok,
            "google-generativeai_version": sdk_version,
        })
        
        st.markdown("**To fix this:**")
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
    
    # Add expandable container styles
    st.markdown("""
    <style>
        .expandable-container {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 24px;
            margin: 16px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            animation: slideDown 0.3s ease-out;
        }
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        .container-close-btn {
            float: right;
            background: transparent;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #64748b;
            padding: 0;
        }
        .container-close-btn:hover {
            color: #0f172a;
        }
    </style>
    """, unsafe_allow_html=True)


def _generate_pdf_report(country: str, period: str, year: str, metrics: Dict) -> bytes:
    """
    Generate a professional PDF report with metrics and timestamp.
    Falls back to HTML if fpdf2 is not available.
    """
    timestamp = pd.Timestamp.now()
    
    # Create simple HTML-based PDF content
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            .header {{ text-align: center; margin-bottom: 30px; border-bottom: 3px solid #10b981; padding-bottom: 20px; }}
            .title {{ font-size: 28px; font-weight: bold; color: #0f172a; }}
            .subtitle {{ font-size: 12px; color: #64748b; margin-top: 10px; }}
            .section {{ margin: 25px 0; page-break-inside: avoid; }}
            .section-title {{ font-size: 16px; font-weight: bold; color: #10b981; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; margin-bottom: 15px; }}
            .metric-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }}
            .metric-label {{ font-weight: bold; color: #64748b; }}
            .metric-value {{ color: #0f172a; font-weight: 600; }}
            .filters {{ background: #f8fafc; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .filter-item {{ padding: 5px 0; }}
            .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 10px; color: #94a3b8; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">💧 Executive Report</div>
            <div class="subtitle">Water Utility Performance Dashboard</div>
            <div class="subtitle">Generated: {timestamp.strftime('%B %d, %Y at %H:%M:%S')}</div>
        </div>
        
        <div class="section">
            <div class="section-title">Report Filters</div>
            <div class="filters">
                <div class="filter-item"><strong>Country:</strong> {country}</div>
                <div class="filter-item"><strong>Time Period:</strong> {period}</div>
                <div class="filter-item"><strong>Year:</strong> {year}</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">Key Performance Indicators</div>
            <div class="metric-row">
                <span class="metric-label">Service Coverage:</span>
                <span class="metric-value">{metrics.get('coverage_score', 'N/A')}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Financial Health:</span>
                <span class="metric-value">{metrics.get('fin_score', 'N/A')}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Operational Efficiency:</span>
                <span class="metric-value">{metrics.get('eff_score', 'N/A')}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Service Quality:</span>
                <span class="metric-value">{metrics.get('qual_score', 'N/A')}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Collection Efficiency:</span>
                <span class="metric-value">{metrics.get('coll_eff', 'N/A')}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">NRW (Non-Revenue Water):</span>
                <span class="metric-value">{metrics.get('nrw', 'N/A')}</span>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">Report Details</div>
            <p>This report provides a snapshot of key performance indicators based on the selected filters.</p>
            <p>For detailed analysis and visualizations, please refer to the interactive dashboard.</p>
        </div>
        
        <div class="footer">
            <p>This is a system-generated report. For more information, visit the Executive Dashboard.</p>
        </div>
    </body>
    </html>
    """
    
    return html_content.encode('utf-8')


def _initialize_expandable_state() -> None:
    """Initialize session state for expandable containers."""
    if "expanded_container" not in st.session_state:
        st.session_state["expanded_container"] = None  # None, "report", or "alerts"
    if "show_alert_settings" not in st.session_state:
        st.session_state["show_alert_settings"] = False


def _render_expandable_container(container_id: str, title: str, content_fn: Callable) -> None:
    """Render an expandable container with close button."""
    is_expanded = st.session_state.get("expanded_container") == container_id
    
    if is_expanded:
        st.markdown(f"""
        <div class="expandable-container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; color: #10b981;">{title}</h3>
                <button class="container-close-btn" onclick="window.location.href='?';" title="Close">✕</button>
            </div>
        """, unsafe_allow_html=True)
        
        content_fn()
        
        st.markdown("</div>", unsafe_allow_html=True)


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
                
                # Remove YTD, only show Quarterly and Monthly
                period = st.radio(
                    "Period",
                    ["Quarterly", "Monthly"],
                    horizontal=True,
                    key="view_period",
                    label_visibility="collapsed"
                )
                
                # Show year selector when Quarterly or Monthly is selected
                if period in ["Quarterly", "Monthly"]:
                    # Use years from actual data, not hardcoded list
                    available_years = sorted([2020, 2021, 2022, 2023, 2024], reverse=True)
                    if "selected_year" not in st.session_state:
                        st.session_state["selected_year"] = available_years[0]
                    # Ensure selected year is valid
                    current_year = st.session_state.get("selected_year", available_years[0])
                    if current_year not in available_years:
                        current_year = available_years[0]
                        st.session_state["selected_year"] = current_year
                    
                    selected_year = st.selectbox(
                        "Year",
                        options=available_years,
                        index=available_years.index(current_year),
                        key="header_year_select",
                        label_visibility="collapsed"
                    )
                    st.session_state["selected_year"] = selected_year
                else:
                    st.session_state["selected_year"] = "All"

            with c3:
                st.markdown('<div style="font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Quick Actions</div>', unsafe_allow_html=True)
                ac1, ac2, ac3 = st.columns(3)
                
                with ac1:
                    # Report Button - toggle expandable container
                    if check_feature_access("export_data"):
                        if st.button("📥 Report", key="btn_report", use_container_width=True, help="View & Download Executive Report"):
                            st.session_state["expanded_container"] = "report" if st.session_state.get("expanded_container") != "report" else None
                            st.rerun()
                    else:
                        st.button("📥 Report", key="btn_report", use_container_width=True, disabled=True, 
                                  help="Export not available for your role")
                
                with ac2:
                    # Meeting Button - disabled with visual styling
                    st.button(
                        "📅 Meeting", 
                        key="btn_meet", 
                        use_container_width=True, 
                        disabled=True, 
                        help="Schedule stakeholder meetings directly from dashboard"
                    )
                
                with ac3:
                    # Alerts Button - toggle expandable container
                    if st.button("🔔 Alerts", key="btn_alert", use_container_width=True, help="Configure Alert Thresholds"):
                        st.session_state["expanded_container"] = "alerts" if st.session_state.get("expanded_container") != "alerts" else None
                        st.rerun()
        
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
    
    # Update Majibot session state based on chat_open status
    if "majibot_open" not in st.session_state:
        st.session_state["majibot_open"] = chat_open
        st.session_state["majibot_status"] = "Active" if chat_open else "Closed"
    else:
        st.session_state["majibot_open"] = chat_open
        st.session_state["majibot_status"] = "Active" if chat_open else "Closed"

    # Initialize expandable state
    _initialize_expandable_state()

    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    if show_header:
        _render_overview_banner()
    
    # Render expandable containers (full-width, below header)
    if st.session_state.get("expanded_container") == "report":
        def render_report_content():
            # Get current filters and metrics from session state
            country = st.session_state.get("selected_country", "All")
            period = st.session_state.get("view_period", "Monthly")
            year = st.session_state.get("selected_year", "All")
            
            # Get metrics from exec insights cache if available
            insights_cache = st.session_state.get("exec_insights_cache", {})
            metrics = {
                "coverage_score": f"{insights_cache.get('coverage_score', 'N/A')}%",
                "fin_score": f"{insights_cache.get('fin_score', 'N/A')}%",
                "eff_score": f"{insights_cache.get('eff_score', 'N/A')}%",
                "qual_score": f"{insights_cache.get('qual_score', 'N/A')}%",
                "coll_eff": f"{insights_cache.get('collection_efficiency', 'N/A')}%",
                "nrw": f"{insights_cache.get('nrw_percent', 'N/A')}%"
            }
            
            st.markdown("**Report Filters:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Country", country)
            with col2:
                st.metric("Period", period)
            with col3:
                st.metric("Year", year)
            
            st.markdown("---")
            st.markdown("**Key Performance Indicators:**")
            kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
            with kpi_col1:
                st.metric("Coverage Score", metrics["coverage_score"])
                st.metric("Financial Health", metrics["fin_score"])
            with kpi_col2:
                st.metric("Efficiency", metrics["eff_score"])
                st.metric("Quality Score", metrics["qual_score"])
            with kpi_col3:
                st.metric("Collection Eff.", metrics["coll_eff"])
                st.metric("NRW", metrics["nrw"])
            
            st.markdown("---")
            
            # Download buttons
            col_download1, col_download2 = st.columns(2)
            with col_download1:
                # HTML Report Download
                html_content = _generate_pdf_report(country, period, year, insights_cache)
                st.download_button(
                    label="📄 Download HTML Report",
                    data=html_content,
                    file_name=f"water_dashboard_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    key="download_html_report"
                )
            
            with col_download2:
                # Text Report Download
                text_content = f"""Executive Report
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

Filters Applied:
- Country: {country}
- Period: {period}
- Year: {year}

Key Metrics:
- Service Coverage: {metrics['coverage_score']}
- Financial Health: {metrics['fin_score']}
- Operational Efficiency: {metrics['eff_score']}
- Service Quality: {metrics['qual_score']}
- Collection Efficiency: {metrics['coll_eff']}
- NRW (Non-Revenue Water): {metrics['nrw']}

For detailed analysis and visualizations, please refer to the interactive dashboard.
"""
                st.download_button(
                    label="📋 Download Text Report",
                    data=text_content,
                    file_name=f"water_dashboard_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    key="download_text_report"
                )
            
            if st.button("Close Report", key="close_report_btn", use_container_width=True):
                st.session_state["expanded_container"] = None
                st.rerun()
        
        _render_expandable_container("report", "📥 Executive Report", render_report_content)
    
    elif st.session_state.get("expanded_container") == "alerts":
        def render_alerts_content():
            st.markdown("**Alert Configuration**")
            st.info("""
            Configure thresholds for system alerts. When metrics fall outside these ranges, 
            you'll receive notifications on the dashboard.
            """)
            
            with st.form("alert_settings_form"):
                col1, col2 = st.columns(2)
                with col1:
                    nrw_threshold = st.slider("NRW Alert Threshold (%)", min_value=10, max_value=50, value=30, step=5)
                    service_hours_threshold = st.slider("Service Hours (hrs/day)", min_value=4, max_value=24, value=12, step=1)
                
                with col2:
                    coll_eff_threshold = st.slider("Collection Efficiency (%)", min_value=30, max_value=90, value=70, step=5)
                    quality_threshold = st.slider("Quality Score (%)", min_value=50, max_value=100, value=80, step=5)
                
                col_submit1, col_submit2 = st.columns(2)
                with col_submit1:
                    if st.form_submit_button("💾 Save Alert Settings", use_container_width=True):
                        st.success("✅ Alert settings saved successfully!")
                
                with col_submit2:
                    if st.form_submit_button("❌ Reset to Defaults", use_container_width=True):
                        st.info("Alert settings reset to default values.")
            
            if st.button("Close Alerts", key="close_alerts_btn", use_container_width=True):
                st.session_state["expanded_container"] = None
                st.rerun()
        
        _render_expandable_container("alerts", "🔔 Alert Settings", render_alerts_content)
    
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
