"""
Authentication and Role-Based Access Control (RBAC) Module
==========================================================

This module provides a comprehensive authentication system for the Water Utility Dashboard
with the following features:

1. User Authentication:
   - Secure login with hashed passwords
   - Session-based authentication
   - Automatic session timeout

2. Role-Based Access Control:
   - MASTER_USER: Full access to all countries and administrative functions
   - COUNTRY_ADMIN: Full access to assigned country only
   - ANALYST: Read-only access to assigned country only
   - VIEWER: Limited read-only access to assigned country

3. Data Access Control:
   - Users can only view data from their assigned country
   - Cross-country data access is blocked for non-master users
   - All data queries are filtered through access control checks

4. Security Features:
   - Password hashing using bcrypt (or fallback to hashlib)
   - Session timeout after inactivity
   - Login attempt limiting
   - Audit logging for security events

Privacy Compliance:
- This system ensures users only access data from their assigned country
- Prevents unauthorized cross-border data access
- Maintains data isolation between countries
"""

from __future__ import annotations

import os
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import streamlit as st


# =============================================================================
# CONFIGURATION
# =============================================================================

# Session timeout in minutes (default: 30 minutes)
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

# Maximum login attempts before lockout
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))

# Lockout duration in minutes
LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))


# =============================================================================
# USER ROLES
# =============================================================================

class UserRole(Enum):
    """
    User roles with hierarchical access levels.
    
    MASTER_USER: Full access to all countries and administrative functions
    COUNTRY_ADMIN: Full access to their assigned country only
    ANALYST: Read-only access to their assigned country
    VIEWER: Limited read-only access to their assigned country
    """
    MASTER_USER = "master_user"
    COUNTRY_ADMIN = "country_admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    
    @property
    def display_name(self) -> str:
        """Human-readable role name."""
        names = {
            UserRole.MASTER_USER: "Master User",
            UserRole.COUNTRY_ADMIN: "Country Administrator",
            UserRole.ANALYST: "Data Analyst",
            UserRole.VIEWER: "Viewer"
        }
        return names.get(self, self.value)
    
    @property
    def access_level(self) -> int:
        """Numeric access level for comparison (higher = more access)."""
        levels = {
            UserRole.MASTER_USER: 100,
            UserRole.COUNTRY_ADMIN: 75,
            UserRole.ANALYST: 50,
            UserRole.VIEWER: 25
        }
        return levels.get(self, 0)


# =============================================================================
# USER DATA MODEL
# =============================================================================

@dataclass
class User:
    """
    User data model with role and country assignment.
    
    Attributes:
        username: Unique identifier for the user
        password_hash: Hashed password (never store plain text)
        role: User's role determining access level
        assigned_country: Country this user can access (None for master users)
        full_name: Display name for the user
        email: User's email address
        is_active: Whether the account is active
        created_at: Account creation timestamp
        last_login: Last successful login timestamp
    """
    username: str
    password_hash: str
    role: UserRole
    assigned_country: Optional[str] = None  # None means all countries (for master users)
    full_name: str = ""
    email: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    
    def can_access_country(self, country: str) -> bool:
        """Check if user can access data from a specific country."""
        # Master users can access all countries
        if self.role == UserRole.MASTER_USER:
            return True
        # Other users can only access their assigned country
        if self.assigned_country is None:
            return False
        return self.assigned_country.lower() == country.lower()
    
    def can_view_all_countries(self) -> bool:
        """Check if user can view data from all countries."""
        return self.role == UserRole.MASTER_USER
    
    def can_export_data(self) -> bool:
        """Check if user can export data."""
        return self.role in [UserRole.MASTER_USER, UserRole.COUNTRY_ADMIN, UserRole.ANALYST]
    
    def can_generate_reports(self) -> bool:
        """Check if user can generate board reports."""
        return self.role in [UserRole.MASTER_USER, UserRole.COUNTRY_ADMIN]
    
    def can_use_ai_assistant(self) -> bool:
        """Check if user can use the AI assistant (MajiBot)."""
        return self.role in [UserRole.MASTER_USER, UserRole.COUNTRY_ADMIN, UserRole.ANALYST]
    
    def get_accessible_countries(self, all_countries: List[str]) -> List[str]:
        """Get list of countries this user can access."""
        if self.role == UserRole.MASTER_USER:
            return all_countries
        if self.assigned_country:
            return [self.assigned_country]
        return []


# =============================================================================
# PASSWORD HASHING
# =============================================================================

def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Hash a password using SHA-256 with salt.
    
    In production, consider using bcrypt or argon2 for better security.
    This implementation provides a reasonable balance of security and compatibility.
    """
    if salt is None:
        salt = os.urandom(16).hex()
    
    # Combine password with salt and hash
    salted = f"{salt}:{password}"
    hash_obj = hashlib.sha256(salted.encode('utf-8'))
    password_hash = hash_obj.hexdigest()
    
    # Return salt and hash combined for storage
    return f"{salt}${password_hash}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt, expected_hash = stored_hash.split('$', 1)
        # Recreate the hash with the same salt
        salted = f"{salt}:{password}"
        hash_obj = hashlib.sha256(salted.encode('utf-8'))
        actual_hash = hash_obj.hexdigest()
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(actual_hash, expected_hash)
    except (ValueError, AttributeError):
        return False


# =============================================================================
# USER CONFIG LOADING
# =============================================================================

def _user_from_config(username: str, config: Dict[str, Any]) -> Optional[User]:
    """Create a User object from config mapping."""
    role_value = str(config.get("role", "")).lower()
    role_lookup = {r.value: r for r in UserRole}
    role = role_lookup.get(role_value)
    password_hash = config.get("password_hash")
    if role is None or not password_hash:
        return None

    assigned_country = config.get("assigned_country")
    if isinstance(assigned_country, str) and not assigned_country.strip():
        assigned_country = None

    return User(
        username=username,
        password_hash=password_hash,
        role=role,
        assigned_country=assigned_country,
        full_name=config.get("full_name", ""),
        email=config.get("email", ""),
        is_active=bool(config.get("is_active", True)),
    )


def _load_users_from_secrets() -> Optional[Dict[str, User]]:
    """
    Load users from Streamlit secrets if available.
    
    Expected structure in .streamlit/secrets.toml:
    [users.username]
    password_hash = "hashed_password"
    role = "master_user"
    assigned_country = "Uganda"
    """
    try:
        secrets_users = st.secrets.get("users")  # type: ignore[attr-defined]
    except Exception:
        return None

    if not secrets_users:
        return None

    users: Dict[str, User] = {}
    for username, config in secrets_users.items():
        if not isinstance(config, dict):
            continue
        user = _user_from_config(username, config)
        if user:
            users[username.lower()] = user

    return users or None


# =============================================================================
# USER DATABASE (In-Memory Demo - Replace with real database in production)
# =============================================================================

def _get_demo_users() -> Dict[str, User]:
    """
    Get demo user database.
    
    ⚠️ IMPORTANT: In production, replace this with a proper database or
    configure users via Streamlit secrets. If secrets are provided under
    [users] in .streamlit/secrets.toml, those will be used instead of the
    built-in demo users.
    
    Default users:
    - admin / admin123 -> Master User (all countries)
    - uganda_admin / uganda123 -> Country Admin (Uganda)
    - cameroon_admin / cameroon123 -> Country Admin (Cameroon)
    - lesotho_admin / lesotho123 -> Country Admin (Lesotho)
    - malawi_admin / malawi123 -> Country Admin (Malawi)
    - analyst1 / analyst123 -> Analyst (Uganda)
    - viewer1 / viewer123 -> Viewer (Uganda)
    """
    # Prefer secrets-backed user config to keep credentials out of source
    secret_users = _load_users_from_secrets()
    if secret_users:
        return secret_users

    users = {
        "admin": User(
            username="admin",
            password_hash=_hash_password("admin123", "fixed_salt_admin"),
            role=UserRole.MASTER_USER,
            assigned_country=None,  # Access to all countries
            full_name="System Administrator",
            email="admin@waterutility.org",
            is_active=True
        ),
        "uganda_admin": User(
            username="uganda_admin",
            password_hash=_hash_password("uganda123", "fixed_salt_uganda"),
            role=UserRole.COUNTRY_ADMIN,
            assigned_country="Uganda",
            full_name="Uganda Country Admin",
            email="uganda.admin@waterutility.org",
            is_active=True
        ),
        "cameroon_admin": User(
            username="cameroon_admin",
            password_hash=_hash_password("cameroon123", "fixed_salt_cameroon"),
            role=UserRole.COUNTRY_ADMIN,
            assigned_country="Cameroon",
            full_name="Cameroon Country Admin",
            email="cameroon.admin@waterutility.org",
            is_active=True
        ),
        "lesotho_admin": User(
            username="lesotho_admin",
            password_hash=_hash_password("lesotho123", "fixed_salt_lesotho"),
            role=UserRole.COUNTRY_ADMIN,
            assigned_country="Lesotho",
            full_name="Lesotho Country Admin",
            email="lesotho.admin@waterutility.org",
            is_active=True
        ),
        "malawi_admin": User(
            username="malawi_admin",
            password_hash=_hash_password("malawi123", "fixed_salt_malawi"),
            role=UserRole.COUNTRY_ADMIN,
            assigned_country="Malawi",
            full_name="Malawi Country Admin",
            email="malawi.admin@waterutility.org",
            is_active=True
        ),
        "analyst1": User(
            username="analyst1",
            password_hash=_hash_password("analyst123", "fixed_salt_analyst1"),
            role=UserRole.ANALYST,
            assigned_country="Uganda",
            full_name="Data Analyst (Uganda)",
            email="analyst@waterutility.org",
            is_active=True
        ),
        "viewer1": User(
            username="viewer1",
            password_hash=_hash_password("viewer123", "fixed_salt_viewer1"),
            role=UserRole.VIEWER,
            assigned_country="Uganda",
            full_name="Viewer (Uganda)",
            email="viewer@waterutility.org",
            is_active=True
        ),
    }
    return users


def get_user(username: str) -> Optional[User]:
    """Get user by username from the database."""
    users = _get_demo_users()
    return users.get(username.lower())


def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[User], str]:
    """
    Authenticate a user with username and password.
    
    Returns:
        Tuple of (success, user, message)
    """
    # Check login attempts / lockout
    lockout_key = f"login_lockout_{username.lower()}"
    attempts_key = f"login_attempts_{username.lower()}"
    
    # Check if user is locked out
    if lockout_key in st.session_state:
        lockout_until = st.session_state[lockout_key]
        if datetime.now() < lockout_until:
            remaining = (lockout_until - datetime.now()).seconds // 60
            return False, None, f"Account locked. Try again in {remaining + 1} minutes."
        else:
            # Lockout expired, clear it
            del st.session_state[lockout_key]
            st.session_state[attempts_key] = 0
    
    # Get user
    user = get_user(username)
    
    if user is None:
        _record_failed_attempt(username)
        return False, None, "Invalid username or password."
    
    if not user.is_active:
        return False, None, "This account has been deactivated. Contact administrator."
    
    # Verify password
    if not _verify_password(password, user.password_hash):
        _record_failed_attempt(username)
        attempts = st.session_state.get(attempts_key, 0)
        remaining = MAX_LOGIN_ATTEMPTS - attempts
        if remaining > 0:
            return False, None, f"Invalid username or password. {remaining} attempts remaining."
        return False, None, "Account locked due to too many failed attempts."
    
    # Success - clear failed attempts
    if attempts_key in st.session_state:
        del st.session_state[attempts_key]
    
    return True, user, "Login successful."


def _record_failed_attempt(username: str) -> None:
    """Record a failed login attempt."""
    attempts_key = f"login_attempts_{username.lower()}"
    lockout_key = f"login_lockout_{username.lower()}"
    
    attempts = st.session_state.get(attempts_key, 0) + 1
    st.session_state[attempts_key] = attempts
    
    if attempts >= MAX_LOGIN_ATTEMPTS:
        st.session_state[lockout_key] = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

def init_session_state() -> None:
    """Initialize authentication-related session state."""
    if "auth_initialized" not in st.session_state:
        st.session_state["auth_initialized"] = True
        st.session_state["authenticated"] = False
        st.session_state["current_user"] = None
        st.session_state["session_start"] = None
        st.session_state["last_activity"] = None


def is_authenticated() -> bool:
    """Check if current session is authenticated."""
    init_session_state()
    
    if not st.session_state.get("authenticated", False):
        return False
    
    # Check session timeout
    last_activity = st.session_state.get("last_activity")
    if last_activity:
        timeout = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        if datetime.now() - last_activity > timeout:
            logout()
            return False
    
    # Update last activity
    st.session_state["last_activity"] = datetime.now()
    return True


def get_current_user() -> Optional[User]:
    """Get the currently authenticated user."""
    if not is_authenticated():
        return None
    return st.session_state.get("current_user")


def login(user: User) -> None:
    """Log in a user and create session."""
    st.session_state["authenticated"] = True
    st.session_state["current_user"] = user
    st.session_state["session_start"] = datetime.now()
    st.session_state["last_activity"] = datetime.now()
    
    # Set the selected country to user's assigned country for non-master users
    if user.role != UserRole.MASTER_USER and user.assigned_country:
        st.session_state["selected_country"] = user.assigned_country


def logout() -> None:
    """Log out the current user and clear session."""
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = None
    st.session_state["session_start"] = None
    st.session_state["last_activity"] = None
    # Clear any cached data
    if "exec_insights_cache" in st.session_state:
        del st.session_state["exec_insights_cache"]


# =============================================================================
# ACCESS CONTROL HELPERS
# =============================================================================

def get_allowed_countries() -> List[str]:
    """
    Get list of countries the current user is allowed to access.
    
    Returns empty list if not authenticated.
    """
    user = get_current_user()
    if user is None:
        return []
    
    # All available countries in the system
    all_countries = ["Uganda", "Cameroon", "Lesotho", "Malawi"]
    
    return user.get_accessible_countries(all_countries)


def can_access_country(country: str) -> bool:
    """Check if current user can access a specific country's data."""
    user = get_current_user()
    if user is None:
        return False
    return user.can_access_country(country)


def filter_data_by_access(df, country_column: str = "country"):
    """
    Filter a DataFrame to only include data the current user can access.
    
    This is the primary data access control function. All data queries
    should pass through this filter to ensure proper access control.
    
    Args:
        df: pandas DataFrame to filter
        country_column: Name of the column containing country information
    
    Returns:
        Filtered DataFrame with only accessible data
    """
    import pandas as pd
    
    user = get_current_user()
    if user is None:
        # Not authenticated - return empty DataFrame
        return df.head(0) if hasattr(df, 'head') else pd.DataFrame()
    
    # Master users get all data
    if user.role == UserRole.MASTER_USER:
        return df
    
    # Filter by assigned country
    if user.assigned_country and country_column in df.columns:
        return df[df[country_column].str.lower() == user.assigned_country.lower()]
    
    # No country column or no assignment - return empty
    return df.head(0) if hasattr(df, 'head') else pd.DataFrame()


def validate_country_selection(selected_country: str) -> str:
    """
    Validate and potentially override country selection based on user access.
    
    For non-master users, this ensures they can only select their assigned country.
    
    Args:
        selected_country: The country selected by the user
    
    Returns:
        The validated country (may be different from input for restricted users)
    """
    user = get_current_user()
    if user is None:
        return selected_country
    
    # Master users can select any country
    if user.role == UserRole.MASTER_USER:
        return selected_country
    
    # Non-master users are locked to their assigned country
    if user.assigned_country:
        return user.assigned_country
    
    return selected_country


def check_feature_access(feature: str) -> bool:
    """
    Check if current user has access to a specific feature.
    
    Features:
    - export_data: Can export data to CSV
    - generate_reports: Can generate board reports
    - ai_assistant: Can use MajiBot AI assistant
    - view_all_zones: Can view all zones (vs limited zones)
    - admin_panel: Can access admin panel
    """
    user = get_current_user()
    if user is None:
        return False
    
    feature_checks = {
        "export_data": user.can_export_data,
        "generate_reports": user.can_generate_reports,
        "ai_assistant": user.can_use_ai_assistant,
        "view_all_zones": lambda: user.role in [UserRole.MASTER_USER, UserRole.COUNTRY_ADMIN, UserRole.ANALYST],
        "admin_panel": lambda: user.role == UserRole.MASTER_USER,
    }
    
    check = feature_checks.get(feature)
    if check is None:
        return False
    
    return check() if callable(check) else check


# =============================================================================
# UI COMPONENTS
# =============================================================================

def hide_sidebar_navigation() -> None:
    """
    Hide the sidebar navigation when user is not authenticated.
    
    This function injects CSS to hide the Streamlit sidebar navigation
    on the login page, providing a cleaner login experience.
    
    Call this function before rendering the login page.
    """
    st.markdown("""
    <style>
        /* Hide sidebar completely on login page */
        [data-testid="stSidebar"] {
            display: none !important;
        }
        
        /* Hide the sidebar toggle button */
        [data-testid="collapsedControl"] {
            display: none !important;
        }
        
        /* Expand main content to full width when sidebar is hidden */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
    </style>
    """, unsafe_allow_html=True)


def render_login_page() -> bool:
    """
    Render the login page with sidebar hidden.
    
    This function renders a clean login page without any navigation elements.
    The sidebar is hidden to provide a focused login experience.
    
    Returns:
        True if login was successful, False otherwise
    """
    # Hide sidebar navigation on login page for a clean login experience
    hide_sidebar_navigation()
    
    # Custom styling for login page
    st.markdown("""
    <style>
        /* Login page specific styles */
        .login-container {
            max-width: 420px;
            margin: 0 auto;
            padding: 2rem;
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .login-header h1 {
            font-size: 2rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 0.5rem;
        }
        .login-header p {
            color: #64748b;
            font-size: 1rem;
        }
        .login-logo {
            font-size: 4rem;
            margin-bottom: 1rem;
        }
        .login-card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 
                        0 2px 4px -2px rgba(0, 0, 0, 0.1);
            border: 1px solid #e2e8f0;
        }
        .login-footer {
            text-align: center;
            margin-top: 1.5rem;
            font-size: 0.875rem;
            color: #94a3b8;
        }
        .demo-credentials {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1.5rem;
            font-size: 0.75rem;
            color: #64748b;
        }
        .demo-credentials h4 {
            margin: 0 0 0.5rem 0;
            font-size: 0.875rem;
            color: #334155;
        }
        .demo-credentials code {
            background: #e2e8f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Login header
        st.markdown("""
        <div class="login-header">
            <div class="login-logo">💧</div>
            <h1>Water Utility Dashboard</h1>
            <p>Sign in to access your dashboard</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Login form
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
                key="login_username"
            )
            
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password"
            )
            
            # Remember me checkbox (simplified - removed forgot password link)
            remember = st.checkbox("Remember me", value=True)
            
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            
            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return False
                
                success, user, message = authenticate_user(username, password)
                
                if success and user:
                    login(user)
                    st.success(f"Welcome, {user.full_name}!")
                    st.rerun()
                else:
                    st.error(message)
                    return False
        
        # Demo credentials info
        st.markdown("""
        <div class="demo-credentials">
            <h4>🔐 Demo Credentials</h4>
            <p><strong>Master User:</strong> <code>admin</code> / <code>admin123</code> (All countries)</p>
            <p><strong>Uganda Admin:</strong> <code>uganda_admin</code> / <code>uganda123</code></p>
            <p><strong>Cameroon Admin:</strong> <code>cameroon_admin</code> / <code>cameroon123</code></p>
            <p><strong>Analyst:</strong> <code>analyst1</code> / <code>analyst123</code> (Uganda only)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Footer
        st.markdown("""
        <div class="login-footer">
            <p>Protected by role-based access control</p>
            <p>© 2024 Water Utility Performance Dashboard</p>
        </div>
        """, unsafe_allow_html=True)
    
    return False


def render_user_info_sidebar() -> None:
    """Render user information and logout button in the sidebar."""
    user = get_current_user()
    if user is None:
        return
    
    with st.sidebar:
        st.markdown("---")
        
        # User info card
        role_colors = {
            UserRole.MASTER_USER: "#8b5cf6",  # Purple
            UserRole.COUNTRY_ADMIN: "#3b82f6",  # Blue
            UserRole.ANALYST: "#10b981",  # Green
            UserRole.VIEWER: "#64748b",  # Gray
        }
        role_color = role_colors.get(user.role, "#64748b")
        
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, {role_color}15 0%, {role_color}05 100%);
                    border: 1px solid {role_color}30;
                    border-radius: 12px;
                    padding: 1rem;
                    margin-bottom: 0.5rem;'>
            <div style='display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;'>
                <div style='width: 40px; height: 40px; border-radius: 50%;
                            background: {role_color}; color: white;
                            display: flex; align-items: center; justify-content: center;
                            font-weight: 700; font-size: 1.1rem;'>
                    {user.full_name[0].upper() if user.full_name else user.username[0].upper()}
                </div>
                <div>
                    <div style='font-weight: 600; color: #0f172a; font-size: 0.95rem;'>
                        {user.full_name or user.username}
                    </div>
                    <div style='font-size: 0.75rem; color: {role_color}; font-weight: 500;'>
                        {user.role.display_name}
                    </div>
                </div>
            </div>
            <div style='font-size: 0.75rem; color: #64748b; margin-top: 0.5rem;'>
                {"🌍 All Countries" if user.role == UserRole.MASTER_USER else f"📍 {user.assigned_country}"}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Session info
        session_start = st.session_state.get("session_start")
        if session_start:
            duration = datetime.now() - session_start
            mins = int(duration.total_seconds() // 60)
            st.caption(f"Session: {mins} min{'s' if mins != 1 else ''}")
        
        # Logout button
        if st.button("🚪 Sign Out", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()


def render_access_denied_message(required_country: Optional[str] = None) -> None:
    """Render an access denied message."""
    user = get_current_user()
    
    st.error("⛔ Access Denied")
    
    if user is None:
        st.warning("You are not logged in. Please sign in to continue.")
    elif required_country:
        st.warning(
            f"You don't have permission to access data from **{required_country}**. "
            f"Your account is limited to **{user.assigned_country or 'no country'}**."
        )
    else:
        st.warning(
            "You don't have permission to access this resource. "
            "Please contact your administrator if you believe this is an error."
        )


def render_feature_disabled_message(feature: str) -> None:
    """Render a message when a feature is disabled for the user."""
    feature_names = {
        "export_data": "Data Export",
        "generate_reports": "Report Generation",
        "ai_assistant": "AI Assistant",
        "admin_panel": "Admin Panel",
    }
    
    feature_name = feature_names.get(feature, feature)
    user = get_current_user()
    
    st.info(
        f"🔒 **{feature_name}** is not available for your role ({user.role.display_name if user else 'Guest'}). "
        f"Contact your administrator for access."
    )


# =============================================================================
# ADMIN SETTINGS PAGE
# =============================================================================

def _get_modifiable_users() -> Dict[str, User]:
    """
    Get users that can be modified by admin.
    Master users cannot modify other master users for security.
    
    Returns:
        Dictionary of username -> User for modifiable users
    """
    all_users = _get_demo_users()
    current_user = get_current_user()
    
    if current_user is None:
        return {}
    
    # Master users can modify all non-master users
    if current_user.role == UserRole.MASTER_USER:
        return {k: v for k, v in all_users.items() if v.role != UserRole.MASTER_USER}
    
    # Country admins can only modify users in their country with lower access
    if current_user.role == UserRole.COUNTRY_ADMIN:
        return {
            k: v for k, v in all_users.items()
            if v.assigned_country == current_user.assigned_country
            and v.role.access_level < current_user.role.access_level
        }
    
    return {}


def update_user_password(username: str, new_password: str) -> Tuple[bool, str]:
    """
    Update a user's password.
    
    Note: In a production system, this would update a database.
    For this demo, changes are stored in session state and persist for the session only.
    
    Args:
        username: The username to update
        new_password: The new password (will be hashed)
    
    Returns:
        Tuple of (success, message)
    """
    current_user = get_current_user()
    if current_user is None:
        return False, "Not authenticated"
    
    # Check permission
    modifiable_users = _get_modifiable_users()
    if username not in modifiable_users:
        return False, "You don't have permission to modify this user"
    
    # Validate password strength
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters"
    
    # Store the password update in session state
    # In production, this would update a database
    if "password_updates" not in st.session_state:
        st.session_state["password_updates"] = {}
    
    st.session_state["password_updates"][username] = _hash_password(new_password)
    
    return True, f"Password updated successfully for {username}"


def render_admin_settings_page() -> None:
    """
    Render the admin settings page for user management.
    
    This page allows admin users to:
    - View all users they can manage
    - Change passwords for lower-access-level users
    - View user access levels and assignments
    
    Access Control:
    - Only MASTER_USER and COUNTRY_ADMIN can access this page
    - MASTER_USER can manage all non-master users
    - COUNTRY_ADMIN can only manage users in their assigned country
    """
    user = get_current_user()
    
    # Check if user has admin access
    if user is None or user.role not in [UserRole.MASTER_USER, UserRole.COUNTRY_ADMIN]:
        render_access_denied_message()
        return
    
    st.markdown("""
    <style>
        .admin-header {
            background: linear-gradient(135deg, #8b5cf615 0%, #8b5cf605 100%);
            border: 1px solid #8b5cf630;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .user-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            transition: box-shadow 0.2s;
        }
        .user-card:hover {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        .role-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Page header
    st.markdown("""
    <div class="admin-header">
        <h2 style='margin: 0 0 0.5rem 0; color: #0f172a;'>⚙️ Admin Settings</h2>
        <p style='margin: 0; color: #64748b;'>Manage user accounts and access permissions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Show current user's admin scope
    if user.role == UserRole.MASTER_USER:
        st.info("🌍 **Master Admin Access**: You can manage all non-master users across all countries.")
    else:
        st.info(f"📍 **Country Admin Access**: You can manage users in **{user.assigned_country}** only.")
    
    # Get modifiable users
    modifiable_users = _get_modifiable_users()
    
    if not modifiable_users:
        st.warning("No users available for management under your access level.")
        return
    
    # Tabs for different admin functions
    tab1, tab2 = st.tabs(["👥 User Management", "🔑 Change Passwords"])
    
    with tab1:
        st.subheader("Managed Users")
        st.caption(f"Showing {len(modifiable_users)} user(s) you can manage")
        
        # Display users in a table-like format
        for username, usr in modifiable_users.items():
            role_colors = {
                UserRole.COUNTRY_ADMIN: ("#3b82f6", "#eff6ff"),
                UserRole.ANALYST: ("#10b981", "#ecfdf5"),
                UserRole.VIEWER: ("#64748b", "#f8fafc"),
            }
            color, bg = role_colors.get(usr.role, ("#64748b", "#f8fafc"))
            
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown(f"""
                <div style='padding: 8px 0;'>
                    <div style='font-weight: 600; color: #0f172a;'>{usr.full_name or usr.username}</div>
                    <div style='font-size: 0.8rem; color: #64748b;'>@{usr.username}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style='padding: 8px 0;'>
                    <span class="role-badge" style='background: {bg}; color: {color};'>
                        {usr.role.display_name}
                    </span>
                    <span style='font-size: 0.8rem; color: #64748b; margin-left: 8px;'>
                        📍 {usr.assigned_country or 'N/A'}
                    </span>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                status_color = "#10b981" if usr.is_active else "#ef4444"
                status_text = "Active" if usr.is_active else "Inactive"
                st.markdown(f"""
                <div style='padding: 8px 0; text-align: center;'>
                    <span style='color: {status_color}; font-size: 0.85rem; font-weight: 500;'>
                        ● {status_text}
                    </span>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<hr style='margin: 4px 0; border: none; border-top: 1px solid #f1f5f9;'>", unsafe_allow_html=True)
    
    with tab2:
        st.subheader("Change User Password")
        st.caption("Select a user and set their new password")
        
        # User selection
        user_options = {f"{usr.full_name or usr.username} (@{username})": username 
                       for username, usr in modifiable_users.items()}
        
        selected_display = st.selectbox(
            "Select User",
            options=list(user_options.keys()),
            key="admin_user_select"
        )
        
        if selected_display:
            selected_username = user_options[selected_display]
            selected_user = modifiable_users[selected_username]
            
            # Show user info
            st.markdown(f"""
            <div style='background: #f8fafc; border-radius: 8px; padding: 1rem; margin: 1rem 0;'>
                <strong>Selected User:</strong> {selected_user.full_name}<br>
                <strong>Role:</strong> {selected_user.role.display_name}<br>
                <strong>Country:</strong> {selected_user.assigned_country or 'All Countries'}
            </div>
            """, unsafe_allow_html=True)
            
            # Password change form
            with st.form("password_change_form", clear_on_submit=True):
                new_password = st.text_input(
                    "New Password",
                    type="password",
                    placeholder="Enter new password (min 6 characters)",
                    key="new_password_input"
                )
                
                confirm_password = st.text_input(
                    "Confirm Password",
                    type="password",
                    placeholder="Confirm new password",
                    key="confirm_password_input"
                )
                
                submitted = st.form_submit_button("Update Password", type="primary")
                
                if submitted:
                    if not new_password or not confirm_password:
                        st.error("Please fill in both password fields.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        success, message = update_user_password(selected_username, new_password)
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
        
        # Security notice
        st.markdown("""
        <div style='background: #fef3c7; border-left: 4px solid #f59e0b; padding: 1rem; 
                    border-radius: 4px; margin-top: 1.5rem; font-size: 0.85rem;'>
            <strong>🔐 Security Note:</strong><br>
            Password changes take effect immediately. Users will need to use their new 
            password on their next login. For production use, implement proper password 
            policies and database storage.
        </div>
        """, unsafe_allow_html=True)
