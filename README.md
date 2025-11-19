# Water Utility Performance Dashboard

## Overview
Streamlit multi‑page dashboard for water and sanitation performance. It visualizes access & coverage, service quality, finance, and production KPIs using Plotly.

## Project Structure
- `Dashboard/`: Streamlit app entrypoint (`Home.py`), pages (`pages/`), and scene logic (`src_page/`).
- `Data/`: Input CSV/JSON files read by the app (see Required Data).
- `Outputs/`: Generated artifacts (e.g., HTML exports from utilities).
- `visualize.py`: CLI helper to generate quick Plotly visuals and export them to `Outputs/`.
- `visualize.ipynb`: Notebook for exploratory visuals.

## Setup
1) Clone and enter the repo
```bash
git clone https://github.com/Akotet08/Applied-Data-Institute.git
cd Applied-Data-Institute
```

2) Create and activate a virtualenv (Python 3.10+ recommended)
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3) Install dependencies
```bash
pip install -r requirements.txt
```

## Run The App
```bash
streamlit run Dashboard/Home.py
```

This launches the multipage app. The sidebar hosts global filters; pages under `Dashboard/pages/` route into scene functions in `Dashboard/src_page/`:
- Access & Coverage → `src_page/access.py` (`scene_access`)
- Service Quality & Reliability → `src_page/quality.py` (`scene_quality`)
- Financial Health → `src_page/finance.py` (`scene_finance`)
- Production → `src_page/production.py` (`scene_production`)
- Sector Overview → `src_page/sector.py` (`scene_sector`)

## Required Data
Place the following files in the `Data/` folder (names must match):
- `Water Access Data.csv`
- `Sewer Access Data.csv`
- `Service_data.csv` (for service quality scene)
- Optional JSONs used by some scenes with sensible fallbacks:
  - `sector_environment.json`
  - `sanitation_chain.json`

## Utilities
Generate standalone visuals to `Outputs/`:
```bash
python visualize.py --country <optional-country-name>
```

## Troubleshooting
- Plotly deprecation warning: “The keyword arguments have been deprecated… Use `config` instead.”
  - We updated all `st.plotly_chart` calls to use `config={...}` and `use_container_width=True` (instead of legacy `width=` kwargs).
  - If you still see this message, search for any remaining direct Plotly kwargs passed to `st.plotly_chart` and move them into `config`.
- Missing files: Errors like “File not found: Data/...csv” mean the expected CSVs aren’t present or named differently. Verify the files under `Data/` match names above.

## Contributing
1) Fork the repository
2) Create a feature branch (`git checkout -b feature/YourFeature`)
3) Commit (`git commit -m "feat: add YourFeature"`)
4) Push (`git push origin feature/YourFeature`)
5) Open a Pull Request

## Branch Strategy
- `main`: Production‑ready
- `develop`: Integration branch
- `feature/*`: New features
- `bugfix/*`: Fixes
- `release/*`: Release prep

## Team Members
- Sadikshya
- Zhomart
- Sinyu — @zerisinyu
- Akotet — @Akotet08

## License
TBD


## Pages → Focus Areas
Each Streamlit page routes to a `scene_*` handler in `Dashboard/src_page/`. When editing, keep these priorities in mind:

1. Access & Coverage (`scene_access`): integrate latest access CSVs, keep ladders and zone grids aligned with filters, and ensure selections flow through visuals.
2. Service Quality & Reliability (`scene_quality`): spotlight DWQ, blockages, and hours; pair charts with concise remediation notes.
3. Financial Health (`scene_finance`): track revenue vs OPEX, NRW, and collection efficiency; guard derived metrics against divide‑by‑zero.
4. Production (`scene_production`): monitor sanitation & reuse chain KPIs; highlight treatment or reuse gaps and efficiency.
