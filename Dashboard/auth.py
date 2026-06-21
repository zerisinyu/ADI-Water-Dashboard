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
from pathlib import Path
import tomllib
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


def _role_value(role) -> str:
    """Return the canonical string value for a role.

    `User` objects stored in `st.session_state` can outlive a Streamlit
    `runOnSave` module reload — when that happens, the cached object's
    `role` attribute is bound to the OLD `UserRole` class while imports
    elsewhere reference the NEW one. `Enum` identity is by class, so
    `user.role == UserRole.MASTER_USER` becomes False even though both
    have value `"master_user"`. Comparing by `.value` (or string fallback)
    sidesteps that trap. Use this for any role gating that may be hit
    after a reload (admin checks, feature flags, etc.).
    """
    if role is None:
        return ""
    # 1. Enum-with-string-value — the canonical happy path.
    v = getattr(role, "value", None)
    if isinstance(v, str) and v:
        return v.lower()
    # 2. Plain string (some session state pickles roundtrip as strings).
    if isinstance(role, str) and role:
        return role.split(".")[-1].lower()
    # 3. Last-ditch repr parsing for an exotic enum class identity churn.
    s = str(role)
    if "." in s:
        return s.split(".")[-1].lower()
    return s.lower()


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
    secrets_users: Optional[Dict[str, Any]] = None
    # First try standard Streamlit secrets
    try:
        secrets_users = st.secrets.get("users")  # type: ignore[attr-defined]
    except Exception:
        secrets_users = None
    
    if not secrets_users:
        secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
        if secrets_path.exists():
            try:
                data = tomllib.loads(secrets_path.read_text())
                secrets_users = data.get("users")  # type: ignore[assignment]
            except Exception:
                secrets_users = None

    if not secrets_users:
        return None

    users: Dict[str, User] = {}
    for username, config in secrets_users.items():
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
    
    ⚠️ IMPORTANT: Credentials are expected to come from Streamlit secrets
    ([users] section in .streamlit/secrets.toml). The hard-coded demo users
    have been removed to avoid shipping passwords in source.
    """
    # Load secrets-backed user config to keep credentials out of source
    secret_users = _load_users_from_secrets()
    if secret_users:
        return secret_users
    
    # If no secrets are configured, return empty dict to avoid embedding passwords in code
    return {}


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
    """Initialize authentication-related session state.

    Idempotent: only sets keys that are missing, never overwrites existing
    values. Earlier versions gated init behind an `auth_initialized` flag
    and *reset* `authenticated`/`current_user` on every fresh init — that
    silently logged users out when navigating between Streamlit multi-page
    scripts if the gate flag was ever lost. `setdefault` avoids that class
    of bug entirely.
    """
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("session_start", None)
    st.session_state.setdefault("last_activity", None)


def is_authenticated() -> bool:
    """Check if current session is authenticated.

    Hardened against multi-page navigation edge cases:
    - If `authenticated` is True but `last_activity` is missing (e.g. the
      session pickle was partially restored after a `runOnSave` reload),
      we re-seed `last_activity` to *now* rather than treating the session
      as expired. Previously a missing `last_activity` could combine with
      a future comparison change to bounce the user back to the login
      screen on a page click.
    - Any non-`datetime` value in `last_activity` is coerced or reset
      instead of raising on the subtraction.
    """
    init_session_state()

    if not st.session_state.get("authenticated", False):
        return False

    # Check session timeout — but only when `last_activity` is a real
    # datetime. Missing / corrupted values are repaired in place.
    last_activity = st.session_state.get("last_activity")
    if isinstance(last_activity, datetime):
        timeout = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        if datetime.now() - last_activity > timeout:
            logout()
            return False
    else:
        st.session_state["last_activity"] = datetime.now()

    # Update last activity on every authenticated access.
    st.session_state["last_activity"] = datetime.now()
    return True


def get_current_user() -> Optional[User]:
    """Get the currently authenticated user.

    Streamlit's `runOnSave` reloads modules in place. A `User` stored in
    `st.session_state` from before the reload still references the *old*
    `UserRole` class, so `user.role == UserRole.MASTER_USER` (using the
    new class) returns False even when both enums have value `"master_user"`.
    Re-bind the role to the current `UserRole` class so role gating
    continues to work across reloads.
    """
    if not is_authenticated():
        return None
    user = st.session_state.get("current_user")
    if user is not None and getattr(user, "role", None) is not None:
        if user.role.__class__ is not UserRole:
            try:
                user.role = UserRole(getattr(user.role, "value", str(user.role)))
            except (ValueError, AttributeError):
                pass
    return user


def login(user: User) -> None:
    """Log in a user and create session."""
    st.session_state["authenticated"] = True
    st.session_state["current_user"] = user
    st.session_state["session_start"] = datetime.now()
    st.session_state["last_activity"] = datetime.now()
    
    # Set the selected country based on user role
    if user.role == UserRole.MASTER_USER:
        # Master users default to "All" - allow full access
        st.session_state["selected_country"] = "All"
    elif user.assigned_country:
        # Non-master users are locked to their assigned country
        st.session_state["selected_country"] = user.assigned_country
    else:
        st.session_state["selected_country"] = "All"


def logout() -> None:
    """Log out the current user and clear session."""
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = None
    st.session_state["session_start"] = None
    st.session_state["last_activity"] = None
    # Clear selected country to prevent persistence issues
    st.session_state["selected_country"] = "All"
    st.session_state["selected_zone"] = "All"
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

        /* Hide Streamlit's top app header (Deploy button + toolbar)
           on the login page so it never overlaps the form. */
        [data-testid="stAppHeader"],
        [data-testid="stHeader"],
        [data-testid="stDecoration"],
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* Expand main content to full width with comfortable top room. */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
            padding-top: 3rem !important;
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

    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            '<div class="login-header">'
            '<div class="login-logo"><span class="icon icon-xl icon-brand">water_drop</span></div>'
            '<h1>Water Utility Dashboard</h1>'
            '<p>Sign in to access your dashboard.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input(
                "Username",
                placeholder="Username",
                key="login_username",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Password",
                key="login_password",
            )
            remember = st.checkbox("Remember me", value=True)

            submitted = st.form_submit_button("Sign in", width="stretch", type="primary")

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return False

                success, user, message = authenticate_user(username, password)

                if success and user:
                    login(user)
                    st.success(f"Welcome, {user.full_name}.")
                    st.rerun()
                else:
                    st.error(message)
                    return False

        st.markdown(
            '<div class="demo-credentials">'
            '<div class="demo-credentials__title">'
            '<span class="icon icon-sm icon-muted">key</span> Demo credentials'
            '</div>'
            '<dl>'
            '<dt>Master</dt><dd><code>admin</code> &nbsp;/&nbsp; <code>admin123</code></dd>'
            '<dt>Uganda admin</dt><dd><code>uganda_admin</code> &nbsp;/&nbsp; <code>uganda123</code></dd>'
            '<dt>Cameroon admin</dt><dd><code>cameroon_admin</code> &nbsp;/&nbsp; <code>cameroon123</code></dd>'
            '<dt>Analyst</dt><dd><code>analyst1</code> &nbsp;/&nbsp; <code>analyst123</code></dd>'
            '</dl>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="login-footer">'
            '<p>Protected by role-based access control</p>'
            '<p>&copy; 2026 ADI Water Utility Dashboard</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    return False


def render_user_info_sidebar() -> None:
    """Render user information and logout button in the sidebar."""
    user = get_current_user()
    if user is None:
        return

    initial = (user.full_name[0] if user.full_name else user.username[0]).upper()
    name = user.full_name or user.username
    role_display = user.role.display_name

    if _role_value(user.role) == "master_user":
        scope_icon, scope_label = "public", "All countries"
    else:
        scope_icon, scope_label = "place", user.assigned_country or "—"

    with st.sidebar:
        st.markdown(
            '<div class="user-card">'
            '<div class="user-card__row">'
            f'<div class="user-card__avatar">{initial}</div>'
            '<div class="user-card__meta">'
            f'<div class="user-card__name">{name}</div>'
            f'<div class="user-card__role">{role_display}</div>'
            '</div>'
            '</div>'
            '<div class="user-card__scope">'
            f'<span class="icon icon-sm icon-muted">{scope_icon}</span>'
            f'<span>{scope_label}</span>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Session info
        session_start = st.session_state.get("session_start")
        if session_start:
            duration = datetime.now() - session_start
            mins = int(duration.total_seconds() // 60)
            st.caption(f"Session: {mins} min{'s' if mins != 1 else ''}")

        # Logout button
        if st.button("Sign out", width="stretch", key="logout_btn", icon=":material/logout:"):
            logout()
            st.rerun()


def render_access_denied_message(required_country: Optional[str] = None) -> None:
    """Render an access denied message."""
    user = get_current_user()
    
    st.error("Access denied")
    
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
        f"**{feature_name}** is not available for your role ({user.role.display_name if user else 'Guest'}). "
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

    Access Control:
    - Only MASTER_USER and COUNTRY_ADMIN can access this page
    - MASTER_USER can manage all non-master users
    - COUNTRY_ADMIN can only manage users in their assigned country
    """
    from utils import render_page_header, render_section_header

    # Resolve current user. `get_current_user()` is the canonical path, but
    # if a Streamlit `runOnSave` reload severs session reads we fall back to
    # the raw session_state value, and finally to the secrets-backed user
    # config keyed by username — that source survives any enum churn.
    user = get_current_user()
    if user is None:
        user = st.session_state.get("current_user")
    role_val = _role_value(getattr(user, "role", None)) if user else ""

    if not role_val and user is not None:
        username = getattr(user, "username", None)
        if username:
            secret_users = _load_users_from_secrets() or {}
            canonical = secret_users.get(username.lower())
            if canonical is not None:
                role_val = _role_value(getattr(canonical, "role", None))
                # Re-bind the session user so subsequent gates also pass.
                user = canonical
                st.session_state["current_user"] = canonical

    if user is None or role_val not in {"master_user", "country_admin"}:
        render_access_denied_message()
        return

    render_page_header(
        "Admin settings",
        eyebrow="Account management",
        subtitle="Manage user accounts, alert thresholds, and pipeline health.",
        icon="settings",
    )

    if role_val == "master_user":
        st.info(
            "**Master admin access** — manage all non-master users across every country."
        )
    else:
        st.info(
            f"**Country admin access** — manage users assigned to **{user.assigned_country or '—'}**."
        )

    modifiable_users = _get_modifiable_users()
    if not modifiable_users:
        st.warning("No users available for management under your access level.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "User management",
        "Change passwords",
        "Alert thresholds",
        "Data quality",
        "Data lineage",
    ])

    # ----- Tab 1: Managed users -----
    with tab1:
        render_section_header(
            "Managed users",
            eyebrow="Directory",
            icon="group",
            meta=f"{len(modifiable_users)} user{'s' if len(modifiable_users) != 1 else ''}",
        )

        role_pill = {
            UserRole.COUNTRY_ADMIN: "brand",
            UserRole.ANALYST: "success",
            UserRole.VIEWER: "neutral",
        }

        for username, usr in modifiable_users.items():
            pill_kind = role_pill.get(usr.role, "neutral")
            status_kind = "success" if usr.is_active else "danger"
            status_text = "Active" if usr.is_active else "Inactive"
            country = usr.assigned_country or "—"

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.markdown(
                    f'<div class="managed-user__name">{usr.full_name or usr.username}</div>'
                    f'<div class="managed-user__handle">@{usr.username}</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    f'<span class="pill pill--{pill_kind}">{usr.role.display_name}</span>'
                    f' <span class="managed-user__country">'
                    f'<span class="icon icon-sm icon-muted">place</span>{country}</span>',
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(
                    f'<span class="pill pill--{status_kind}">{status_text}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown('<hr class="managed-user__divider">', unsafe_allow_html=True)

    # ----- Tab 2: Change password -----
    with tab2:
        render_section_header(
            "Change user password",
            eyebrow="Credentials",
            icon="key",
        )

        user_options = {
            f"{usr.full_name or usr.username} (@{username})": username
            for username, usr in modifiable_users.items()
        }
        selected_display = st.selectbox(
            "Select user",
            options=list(user_options.keys()),
            key="admin_user_select",
        )

        if selected_display:
            selected_username = user_options[selected_display]
            selected_user = modifiable_users[selected_username]

            st.markdown(
                '<div class="card card--quiet" style="margin-top: 0.75rem;">'
                f'<div><strong>{selected_user.full_name or selected_user.username}</strong> '
                f'<span class="pill pill--{role_pill.get(selected_user.role, "neutral")}">'
                f'{selected_user.role.display_name}</span></div>'
                f'<div class="managed-user__country" style="margin-top: 6px;">'
                f'<span class="icon icon-sm icon-muted">place</span>'
                f'{selected_user.assigned_country or "All countries"}</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            with st.form("password_change_form", clear_on_submit=True):
                new_password = st.text_input(
                    "New password",
                    type="password",
                    placeholder="Enter new password (min 6 characters)",
                    key="new_password_input",
                )
                confirm_password = st.text_input(
                    "Confirm password",
                    type="password",
                    placeholder="Confirm new password",
                    key="confirm_password_input",
                )
                submitted = st.form_submit_button("Update password", type="primary")

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
                            st.success(message)
                        else:
                            st.error(message)

        st.markdown(
            '<div class="card card--quiet" style="margin-top: 1.25rem;">'
            '<div style="display: flex; gap: 8px; align-items: flex-start;">'
            '<span class="icon icon-lg icon-muted">lock</span>'
            '<div>'
            '<strong>Security note</strong><br>'
            '<span style="color: var(--text-secondary); font-size: var(--text-caption);">'
            'Password changes take effect immediately. Users will need to use their new '
            'password on their next login. In production, back this with a real database '
            'and a password policy.'
            '</span>'
            '</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

    # ----- Tab 3: Alert thresholds -----
    with tab3:
        render_section_header(
            "Alert thresholds",
            eyebrow="Operations",
            icon="tune",
            meta="Applies to the current session",
        )

        from ai_insights import ALERT_THRESHOLDS

        saved = st.session_state.get("custom_alert_thresholds", {})
        updated_any = False

        for metric_key, cfg in ALERT_THRESHOLDS.items():
            label = metric_key.replace("_", " ").title()
            direction = cfg["direction"]
            unit = cfg["unit"]

            with st.expander(f"**{label}** ({unit})", expanded=False):
                st.caption(
                    "Higher is better" if direction == "higher_is_better" else "Lower is better"
                )
                saved_metric = saved.get(metric_key, {})
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    crit = st.number_input(
                        "Critical",
                        value=float(saved_metric.get("critical", cfg["critical"])),
                        key=f"thresh_{metric_key}_crit",
                    )
                with col_b:
                    warn = st.number_input(
                        "Warning",
                        value=float(saved_metric.get("warning", cfg["warning"])),
                        key=f"thresh_{metric_key}_warn",
                    )
                with col_c:
                    good = st.number_input(
                        "Good",
                        value=float(saved_metric.get("good", cfg["good"])),
                        key=f"thresh_{metric_key}_good",
                    )

                if crit != cfg["critical"] or warn != cfg["warning"] or good != cfg["good"]:
                    saved[metric_key] = {"critical": crit, "warning": warn, "good": good}
                    updated_any = True

        if st.button("Save thresholds", type="primary", icon=":material/save:"):
            st.session_state["custom_alert_thresholds"] = saved
            for mk, overrides in saved.items():
                if mk in ALERT_THRESHOLDS:
                    ALERT_THRESHOLDS[mk].update(overrides)
            st.success("Thresholds saved and applied to the current session.")

        if updated_any:
            st.info("You have unsaved threshold changes. Click **Save thresholds** to apply.")

    # ----- Tab 4: Data quality -----
    with tab4:
        render_section_header(
            "Data quality",
            eyebrow="ETL pipeline",
            icon="rule",
        )

        try:
            from data.pipeline import get_last_run
            from data.database import get_table_stats

            last_run = get_last_run()
            stats = get_table_stats()

            import pandas as _pd
            stats_df = _pd.DataFrame(stats)
            st.markdown("##### Table statistics")
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

            if last_run:
                status_kind = "success" if last_run.success else "danger"
                status_label = "Success" if last_run.success else "Failed"
                st.markdown(
                    f'<div class="card card--quiet" style="margin: 0.75rem 0;">'
                    f'<strong>Last pipeline run</strong> · '
                    f'{last_run.started_at:%Y-%m-%d %H:%M:%S} · '
                    f'{last_run.duration_seconds:.2f}s · '
                    f'<span class="pill pill--{status_kind}">{status_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if last_run.validation_results:
                    st.markdown("##### Validation results")
                    for tbl, vr in last_run.validation_results.items():
                        kind = "success" if vr["valid"] else "warning"
                        label_text = "PASS" if vr["valid"] else "WARN"
                        with st.expander(f"{tbl} — {vr['row_count']} rows", expanded=False):
                            st.markdown(
                                f'<span class="pill pill--{kind}">{label_text}</span>',
                                unsafe_allow_html=True,
                            )
                            if vr["valid"]:
                                st.success("All schema checks passed")
                            else:
                                for err in vr["errors"][:10]:
                                    st.warning(err)

                if last_run.errors:
                    st.markdown("##### Pipeline errors")
                    for err in last_run.errors:
                        st.error(err)
            else:
                st.info("No pipeline run recorded yet. The pipeline runs automatically on first page load.")
        except Exception as exc:
            st.error(f"Could not load pipeline status: {exc}")

    # ----- Tab 5: Data lineage -----
    with tab5:
        render_section_header(
            "Data lineage",
            eyebrow="Pipeline graph",
            icon="account_tree",
        )

        try:
            from data.lineage import render_data_lineage
            render_data_lineage(height=550)
        except Exception as exc:
            st.error(f"Could not render lineage diagram: {exc}")
