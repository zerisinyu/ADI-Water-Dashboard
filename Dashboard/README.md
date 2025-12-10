# Water Utility Performance Dashboard

A multi-page Streamlit dashboard for Water Utility Performance monitoring with role-based access control (RBAC), AI-powered insights, and comprehensive data visualization.

## 🚀 Quick Start

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the dashboard:
```bash
cd Dashboard
streamlit run Home.py
```

3. Open your browser to `http://localhost:8501`

---

## 📖 How to Use This Dashboard

### Getting Started

1. **Login**: Enter your credentials on the login page. Contact your administrator for access.
2. **Navigate**: Use the sidebar to switch between different dashboard pages.
3. **Filter Data**: Use the country, zone, year, and month filters in the sidebar to drill down into specific data.
4. **Export**: Most pages have export buttons to download data as CSV.

### Dashboard Pages

| Page | What It Shows | Key Features |
|------|---------------|---------------|
| **Home (Executive)** | High-level KPIs and performance overview | AI insights, performance trends, board brief generator |
| **Access & Coverage** | Water and sanitation access ladder | JMP standards visualization, equity analysis |
| **Service Quality** | Water quality, complaints, service hours | Compliance tracking, trend analysis |
| **Financial Health** | Revenue, collection efficiency, costs | Cost recovery metrics, zone comparisons |
| **Production** | Water production, NRW, capacity utilization | Daily/monthly trends, source analysis |

### Using MajiBot (AI Assistant)

Click the 🤖 chat icon in the bottom-right corner to open MajiBot. You can ask questions like:

- **"Top 5 zones with highest NRW"** - Get rankings without needing AI
- **"Compare all zones"** - See a comparison table
- **"Show me alerts"** - View current threshold breaches
- **"What is the status of all zones?"** - Get a summary

### Generating Reports

On the Executive page, scroll to "Executive Reporting" section:
1. Set the report period
2. Click "Generate Report"
3. Download as Markdown or Plain Text

---

## 🔐 Authentication System

### User Roles

| Role | Access Level | Description |
|------|--------------|-------------|
| **Master User** | Full Access | Can view all countries, manage all non-master users, access admin settings |
| **Country Admin** | Country-Specific | Full access to assigned country only, can manage lower-level users in their country |
| **Analyst** | Read-Only | Can view and export data for assigned country only |
| **Viewer** | Limited | Read-only access to assigned country with limited features |

### Login Flow

1. **Navigate to Dashboard**: When accessing any page, unauthenticated users are redirected to the login page
2. **Enter Credentials**: Input your username and password (contact your administrator)
3. **Access Granted**: Upon successful login, the sidebar navigation appears and you can access dashboard features based on your role
4. **Session Management**: Sessions timeout after 30 minutes of inactivity

### Post-Login Features

After successful authentication, users can access:

- **Executive Dashboard**: High-level KPIs and performance metrics
- **Access & Coverage**: Water and sewer access data visualization
- **Service Quality**: Quality metrics and reliability analysis
- **Financial Health**: Billing, revenue, and financial KPIs
- **Production**: Water production and operational data
- **Admin Settings** (Admin only): User management and password changes

### Data Access Control

- **Country Filtering**: Non-master users only see data from their assigned country
- **Cross-Country Prevention**: Users cannot access or compare data from other countries
- **Filter Restrictions**: Country selectors are locked for non-master users
- **Audit Trail**: All access is logged for security compliance

---

## 📁 Project Structure

Pages under `Dashboard/pages/` route into scene handlers defined in `Dashboard/src_page/`:

| Page | Handler | Description |
|------|---------|-------------|
| 2_🗺️_Access_&_Coverage | `src_page/access.py` | Water and sewer access visualization |
| 3_🛠️_Service_Quality_&_Reliability | `src_page/quality.py` | Service quality metrics |
| 4_💹_Financial_Health | `src_page/finance.py` | Financial dashboard |
| 5_♻️_Production | `src_page/production.py` | Production operations |
| 6_⚙️_Admin_Settings | `auth.py` | User management (Admin only) |

## 📊 Data Files

Data files are expected in `Data/` at the repo root:
- `Water Access Data.csv`, `Sewer Access Data.csv`, `Service_data.csv`
- `billing.csv`, `financial_services.csv`, `production.csv`
- Optional: `sector_environment.json`, `sanitation_chain.json`

## ⚙️ Admin Settings

The Admin Settings page (`6_⚙️_Admin_Settings`) provides:

### For Master Users:
- View all non-master users across all countries
- Change passwords for any non-master user
- View user roles and country assignments

### For Country Admins:
- View users in their assigned country only
- Change passwords for analysts and viewers in their country
- Cannot modify other admins or master users

### Security Features:
- Password changes take effect immediately
- Minimum password length: 6 characters
- Session-based authentication with timeout
- Login attempt limiting and account lockout

---

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_TIMEOUT_MINUTES` | 30 | Session timeout in minutes |
| `MAX_LOGIN_ATTEMPTS` | 5 | Failed attempts before lockout |
| `LOCKOUT_DURATION_MINUTES` | 15 | Account lockout duration |
| `ENABLE_CHAT_WIDGET` | true | Enable/disable AI assistant |
| `CHAT_MAX_TURNS` | 20 | Maximum chat turns per session |

---

## Notes

- Plotly config is passed via `config={...}` and charts use `use_container_width=True`
- The sidebar is hidden on the login page for a cleaner login experience
- All data queries pass through access control filters automatically
