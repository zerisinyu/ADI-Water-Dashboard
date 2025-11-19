# Dashboard

Run the multi‑page Streamlit app from the repo root:
```bash
streamlit run Dashboard/Home.py
```

Pages under `Dashboard/pages/` route into scene handlers defined in `Dashboard/src_page/`:
- 2_🗺️_Access_&_Coverage → `src_page/access.py` (`scene_access`)
- 3_🛠️_Service_Quality_&_Reliability → `src_page/quality.py` (`scene_quality`)
- 4_💹_Financial_Health → `src_page/finance.py` (`scene_finance`)
- 5_♻️_Production → `src_page/production.py` (`scene_production`)
- Sector & Governance are available via the Home scene when enabled.

Data files are expected in `Data/` at the repo root:
- `Water Access Data.csv`, `Sewer Access Data.csv`, `Service_data.csv`
- Optional: `sector_environment.json`, `sanitation_chain.json`

Notes
- Plotly config is passed via `config={...}` and charts use `use_container_width=True` to avoid deprecated kwargs warnings in older Streamlit versions.
