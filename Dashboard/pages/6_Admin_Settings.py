"""
Admin Settings Page
===================

This page provides administrative functions for managing user accounts.
Access is restricted to users with MASTER_USER or COUNTRY_ADMIN roles.

Features:
- View all managed users
- Change passwords for lower-access-level users
- View user access levels and country assignments

Access Control:
- MASTER_USER: Can manage all non-master users across all countries
- COUNTRY_ADMIN: Can only manage users in their assigned country with lower access
- ANALYST/VIEWER: Cannot access this page
"""

import streamlit as st
from Home import render_scene_page

# Render the admin settings page with authentication check
render_scene_page("admin")
