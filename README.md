# ADI Water Utility Performance Platform

> An executive analytics platform for African water utilities — bringing **role-based dashboards**, **forecast-driven planning**, and an **AI data assistant** to managing directors who currently rely on monthly PDF reports.

<p align="left">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-1.50-FF4B4B?logo=streamlit&logoColor=white">
  <img alt="DuckDB" src="https://img.shields.io/badge/DuckDB-OLAP-FFF000?logo=duckdb&logoColor=black">
  <img alt="Pandera" src="https://img.shields.io/badge/Pandera-schema-success">
  <img alt="StatsForecast" src="https://img.shields.io/badge/StatsForecast-AutoARIMA%2FETS-3F88C5">
  <img alt="scikit-learn" src="https://img.shields.io/badge/scikit--learn-IsolationForest-F7931E?logo=scikitlearn&logoColor=white">
  <img alt="Plotly" src="https://img.shields.io/badge/Plotly-charts-3F4F75?logo=plotly&logoColor=white">
  <img alt="LLMs" src="https://img.shields.io/badge/LLM-Gemini%20%7C%20Grok%20%7C%20GLM-7c3aed">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-informational">
</p>

---

## Why this project

Water utilities in sub-Saharan Africa run on data that nobody reads. KPIs sit in spreadsheets that arrive too late, and decisions get made on intuition. This platform turns that data into a **live operating cockpit**:

| Audience | What they get |
|---|---|
| **Managing Director** | One screen with executive KPIs, a daily AI briefing, and natural-language Q&A over the warehouse. |
| **Country Administrator** | Country-scoped dashboards (Access, Service Quality, Finance, Production) with drill-downs. |
| **Analyst** | A forecasting workbench (12-month ARIMA/ETS), anomaly detection, and scenario simulations. |
| **Board / Investor** | One-click PDF and Word reports with charts, narrative, and lineage. |

> 📘 For an end-user walkthrough of every screen and every formula, see **[Dashboard User Manual](./Dashboard%20Manual.md)** (also available as `documentation.pdf`).

---

## Highlights — what this project demonstrates

This is a **data engineering + AI** portfolio piece. The interesting parts are below the dashboard.

### 🧱 Data engineering
- **ETL pipeline** with structured logging, schema validation, and incremental reload
  (`Dashboard/data/pipeline.py`).
- **DuckDB** as the in-process analytical warehouse — sub-second SQL over millions of
  billing rows, no external service required (`Dashboard/data/database.py`).
- **Pandera** schemas enforce typed contracts on every CSV at ingest time
  (`Dashboard/data/schemas.py`).
- **Derived-metric views** — NRW%, collection efficiency, service quality index,
  capacity utilisation — computed once in DuckDB and reused everywhere
  (`v_billing_monthly`, `v_production_monthly`, `v_nrw_monthly`, `v_service_quality`).
- **Lineage view** that maps every KPI back to its source CSV and formula
  (`Dashboard/data/lineage.py`).

### 🤖 AI surface
- **MajiBot** — a floating chat assistant (Intercom-style) wired to three providers
  out of the box: **Google Gemini**, **xAI Grok**, **Zhipu GLM**. Provider, model, and
  API key are persisted per-user in a chmod-0600 keystore.
- **Text-to-SQL fallback** — questions that don't match a fast pattern go through
  the LLM with the live DuckDB schema as context, then the generated SQL is executed
  against the warehouse (`Dashboard/llm.py::generate_sql`).
- **RAG over indicators** — semantic retrieval of metric definitions so the assistant
  answers with the *correct* formula, not a hallucinated one (`Dashboard/data/rag.py`).
- **Streaming responses** with auto-scroll, suggested questions seeded from the
  current dashboard state, and a 16-message rolling history window.

### 📈 Forecasting & ML
- **AutoARIMA + AutoETS** model selection per metric with **80%/95% confidence
  bands** (`Dashboard/analytics/forecasting.py`). Falls back to linear regression
  if the seasonal models can't converge.
- **Anomaly detection** ensemble — Z-score, IQR, and Isolation Forest
  (`Dashboard/analytics/anomaly_detection.py`).
- **STL decomposition** for trend / seasonality / residual on every KPI series.
- **Scenario simulator** — what-if engine for NRW reduction, tariff changes,
  and coverage expansion with payback analysis
  (`Dashboard/analytics/scenarios.py`).

### 🔐 Security & access control
- **Salted SHA-256** password hashes; failed-attempt lockout (`Dashboard/auth.py`).
- **Four roles** (Master / Country Admin / Analyst / Viewer) with country-scoped
  data filtering enforced at the data-access layer, not just in the UI.
- **Feature gates** for AI assistant, export, and admin — declared per role.
- **No secrets in source** — credentials live in `.streamlit/secrets.toml` or
  environment variables.

### ✅ Testing
- Pytest suite covering ETL transformations, Pandera schemas, anomaly detection,
  forecasting math, and the natural-language query parser. See `tests/`.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Streamlit UI (multi-page)                       │
│   Executive · Access · Quality · Finance · Production · Forecasting   │
│   Floating MajiBot · Daily briefing · PDF/Word export                 │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │                               │
        ┌───────▼──────────┐         ┌──────────▼──────────┐
        │  ai_insights /   │         │  analytics/         │
        │  ChatLLM (llm.py)│         │  forecasting /      │
        │  • Gemini / Grok │         │  anomaly_detection /│
        │  • text-to-SQL   │         │  decomposition /    │
        │  • RAG retriever │         │  scenarios          │
        └───────┬──────────┘         └──────────┬──────────┘
                │                               │
                └──────────────┬────────────────┘
                               │ SQL
                ┌──────────────▼──────────────┐
                │      DuckDB (in-process)     │
                │  Views: v_billing_monthly,   │
                │         v_production_monthly,│
                │         v_nrw_monthly,       │
                │         v_service_quality    │
                └──────────────┬──────────────┘
                               │ ETL: extract → validate → transform
                ┌──────────────▼──────────────┐
                │   Pandera schemas + loaders │
                │   (data/pipeline.py)        │
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │   CSV / JSON / GeoJSON      │
                │   in /Data                  │
                └─────────────────────────────┘
```

---

## Repository layout

```
.
├── Dashboard/                  # Streamlit application
│   ├── Home.py                 # Entry point, layout, MajiBot panel/FAB
│   ├── auth.py                 # RBAC: users, roles, gates, login UI
│   ├── llm.py                  # Multi-provider chat client + text-to-SQL
│   ├── ai_insights.py          # NLQ parser, anomalies, daily-pulse generator
│   ├── utils.py                # Loaders, header chrome, shared widgets
│   ├── charts.py               # Plotly chart factories
│   ├── styles.css              # Design system (~50 KB of scoped CSS)
│   ├── data/
│   │   ├── database.py         # DuckDB connection + table registry
│   │   ├── pipeline.py         # ETL orchestrator (extract/validate/transform)
│   │   ├── schemas.py          # Pandera schemas per table
│   │   ├── lineage.py          # KPI → source-CSV lineage graph
│   │   ├── rag.py              # Indicator embedding + retrieval
│   │   └── keystore.py         # 0600 chmod API-key store
│   ├── analytics/
│   │   ├── forecasting.py      # AutoARIMA + AutoETS + linear fallback
│   │   ├── anomaly_detection.py# Z-score, IQR, Isolation Forest
│   │   ├── decomposition.py    # STL trend/season/residual
│   │   └── scenarios.py        # NRW / tariff / coverage what-if
│   ├── components/             # Geo map, benchmarking card, PDF export
│   ├── src_page/               # Per-scene render functions
│   └── pages/                  # Streamlit multipage routing shims
├── Data/                       # Source CSV + GeoJSON (committed for reproducibility)
├── tests/                      # Pytest suite
├── Dashboard Manual.md         # End-user manual (PDF source)
├── documentation.pdf           # Pre-built end-user manual
├── Dockerfile · docker-compose.yml
└── requirements.txt · pyproject.toml
```

---

## Getting started

### 1. Clone and install

```bash
git clone https://github.com/zerisinyu/ADI-Water-Dashboard.git
cd ADI-Water-Dashboard

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp secrets.toml.example Dashboard/.streamlit/secrets.toml
```

Then open `Dashboard/.streamlit/secrets.toml` and fill in:
- `[users.*]` — at least one master user with a salted SHA-256 password hash
  (use the helper in `auth.py::_hash_password`).
- Optional: `GEMINI_API_KEY`, `GROK_API_KEY`, `GLM_API_KEY`. Users can also paste
  their own keys from the MajiBot settings panel at runtime (persisted to
  `~/.adi_water_dashboard/keys.json`, chmod 0600).

### 3. Run

```bash
streamlit run Dashboard/Home.py
```

Visit http://localhost:8501. The shipped `secrets.toml.example` includes demo
credentials (`admin / admin123`, etc.) — **rotate or delete these before any
real deployment.**

### 4. Run with Docker

```bash
docker compose up --build
```

### 5. Run the tests

```bash
pytest
```

---

## Configuration reference

| Env var | Purpose | Default |
|---|---|---|
| `DUCKDB_PATH` | Path to persistent DuckDB file. Use `:memory:` for ephemeral. | `:memory:` |
| `GEMINI_API_KEY` / `GROK_API_KEY` / `GLM_API_KEY` | LLM provider keys. | unset |
| `CHAT_MAX_TURNS` | Cap on user messages per chat session. | `20` |
| `DISABLE_PANDERA_IMPORT_WARNING` | Silence the upstream future-warning. | unset |

---

## Roadmap

- [x] DuckDB warehouse + Pandera validation
- [x] AutoARIMA / AutoETS forecasting per metric, per country
- [x] Multi-provider LLM with text-to-SQL fallback
- [x] Role-based access control with country scoping
- [x] Persistent API-key store + per-user provider selection
- [ ] Background job runner for nightly ETL (replace startup-time init)
- [ ] Postgres write-through for shared persistence in multi-user deploys
- [ ] Embedding-based RAG with on-disk vector index

---

## Credits

Built by the Applied Data Institute team.

| | |
|---|---|
| Engineering | Sinyu — [@zerisinyu](https://github.com/zerisinyu), Akotet — [@Akotet08](https://github.com/Akotet08) |
| Data & analysis | Sadikshya, Zhomart |

Datasets are stylised / synthetic where required and based on publicly reported
indicators. Released under the MIT license — see `LICENSE`.
