Water Utility Performance Dashboard — Scene Updates to Cover Full KPI Set
(Fusion 4) — TEXT SPEC FOR DEVELOPERS
===============================================================================

Purpose
-------
This update expands and formalizes the storyboard so that **every KPI** in the provided list is introduced in a concrete scene with: component placement, formula, direction of good performance, data source placeholder, update frequency, and a minimal mock-data schema.

Global Conventions
------------------
- Time grain: monthly for ops/finance/sanitation; annual for national/sector KPIs unless stated.
- Direction: ↑ good, ↓ good flags explicitly listed per KPI.
- Units: % unless otherwise stated; hours/day, l/c/d, KSh, m³, counts.
- Filters: {zone, date_range}; filters persist across scenes via FilterContext.
- Benchmarks (defaults – adjust per regulator): NRW ≤ 25, DWQ ≥ 95, Hours ≥ 22, Collection ≥ 95, O&M ≥ 150.
- Data sources (placeholders): {household_survey, utility_ops, utility_finance, lab_results, asset_register, national_accounts}.

Navigation (unchanged)
----------------------
Executive Summary (Scene 1)
  ├─▶ Access & Coverage (Scene 2)
  ├─▶ Service Quality & Reliability (Scene 3)
  ├─▶ Financial Health (Scene 4)
  ├─▶ Sanitation & Reuse Chain (Scene 5)  ← NEW explicit scene
  ├─▶ Governance & Compliance (Scene 6)   ← NEW explicit scene
  └─▶ Sector & Environment (Scene 7)      ← NEW explicit scene

===============================================================================
SCENE 1 — Executive Summary (Landing)
===============================================================================
Purpose: One-glance health for leaders; introduces headline KPIs and alerts.
Layout:
- Row 1: 5 Scorecards (Gauges): Safely Managed Water %, Safely Managed Sanitation %, Collection Efficiency %, Operating Cost Coverage %, NRW %.
- Row 2: Asset Health Index (gauge), Hours of Supply (gauge), DWQ % (gauge), Customer Satisfaction (optional).
- Row 3: AlertBanner + Quick Stats (population served, connections, active staff).

KPIs Introduced (with direction, formula, mock source, freq):
1) % population with safely managed water (↑ good)
   = improved_on_premises_available_safe / total_population * 100
   source: household_survey + lab_results; freq: annual/quarter
2) % population with safely managed sanitation (↑ good)
   = improved_unshared_safely_disposed / total_population * 100
   source: household_survey + sanitation_chain; freq: annual/quarter
3) Revenue collection efficiency % (↑ good)
   = revenue_collected / revenue_billed * 100
   source: utility_finance; freq: monthly
4) Operating cost coverage % (↑ good)
   = revenue / opex * 100
   source: utility_finance; freq: monthly
5) Non-Revenue Water % (↓ good)
   = (volume_produced - volume_billed) / volume_produced * 100
   source: utility_ops + billing; freq: monthly
6) Asset Health Index (↑ good)
   = good_condition_assets / total_assets * 100
   source: asset_register; freq: quarter
7) Hours of Supply (↑ good)
   = avg_service_hours_per_day
   source: utility_ops; freq: monthly
8) Drinking Water Quality (DWQ) % (↑ good)
   = tests_meeting_standard / tests_total * 100
   source: lab_results; freq: monthly

Mock Data (minimal):
executive_summary.json
{
  "month":"2025-08",
  "water_safe_pct":59,
  "san_safe_pct":31,
  "collection_eff_pct":94,
  "om_coverage_pct":98,
  "nrw_pct":44,
  "asset_health_idx":72,
  "hours_per_day":20.3,
  "dwq_pct":96
}

===============================================================================
SCENE 2 — Access & Coverage (JMP ladders + utility coverage dynamics)
===============================================================================
Purpose: Show who is served and where; include full JMP ladders + utility coverage expansion KPIs.
Layout:
- Left: Choropleth Map (zone -> safely managed water %; toggle to sanitation).
- Right Top: Two Stacked Bars: Water ladder (surface/unimproved/limited/basic/safely), Sanitation ladder (open defecation/unimproved/limited/basic/safely).
- Right Bottom: Coverage Dynamics Cards and Line (coverage %, % increase, piped connections growth, sewered connections %, % increase). Gap panel shows people without access.

KPIs Introduced (with direction, formula, source, freq):
Water ladder (all ↑ good except “surface” which ↓ good):
A1) % population with access to surface water (↓ good)
A2) % population with unimproved water sources (↓ good)
A3) % population with access to limited water sources (↓ good)
A4) % population with access to basic water sources (↑ good)
A5) % population with access to safely managed water (↑ good)
Sanitation ladder:
A6) % population practicing open defecation (↓ good)
A7) % population with unimproved sanitation facilities (↓ good)
A8) % population with limited sanitation facilities (↓ good)
A9) % population with basic sanitation facilities (↑ good)
A10) % population with safely managed sanitation facilities (↑ good)
All ladders source: household_survey (+ lab for safely managed water); freq: annual/quarter for dashboard.

Utility coverage dynamics (↑ good unless noted):
B1) % water supply coverage (↑) 
   Option (household): households_dep_on_municipal / total_households * 100
   Option (area): area_covered_piped / total_area * 100
   source: utility_ops + planning; freq: quarter
B2) % increase in water supply coverage (↑)
   = (coverage_new - coverage_old)/coverage_old * 100
   source: same; freq: quarter
B3) % increase in piped water supply (↑)
   = (new_piped_conns - old_piped_conns)/old_piped_conns * 100
   source: utility_ops; freq: month/quarter
B4) % sewered connections (↑)
   = sewered_households / total_households * 100
   source: utility_ops; freq: quarter
B5) % of increase in sewered connections (↑)
   = (new_sewered - old_sewered)/old_sewered * 100
   source: utility_ops; freq: quarter

Mock Data (minimal):
access_coverage.json
{
  "zones":[
    {"zone":"A","pop":25000,"water_ladder":{"surface":6,"unimproved":8,"limited":16,"basic":20,"safely":50},"san_ladder":{"open_def":5,"unimproved":12,"limited":24,"basic":41,"safely":18}},
    {"zone":"B","pop":30000,"water_ladder":{"surface":4,"unimproved":7,"limited":21,"basic":25,"safely":43},"san_ladder":{"open_def":4,"unimproved":10,"limited":22,"basic":45,"safely":19}}
  ],
  "coverage":{"pct_water":68,"pct_sewered":22},
  "dynamics":{"pct_water_growth":3.1,"pct_piped_growth":4.7,"pct_sewered_growth":2.4}
}

===============================================================================
SCENE 3 — Service Quality & Reliability (Ops safety + continuity)
===============================================================================
Purpose: Monitor water quality, continuity, consumption, interruptions, and complaints.
Layout:
- Row 1: Line (DWQ %), Line (Hours/day). 
- Row 2: KPI cards: 24x7 supply %, Complaints resolution efficiency %, Complaints turnaround time (days).
- Row 3: Bar: Sewer blockages per 100 km (or per 1000 connections). Scatter: Consumption per capita vs hours.

KPIs Introduced:
C1) Water Quality % (↑ good) = tests_meeting_standard / tests_total * 100  (lab_results, monthly)
C2) Continuity of supply (↑) = hours_supplied_per_day (utility_ops, monthly)
C3) 24×7 water supply % (↑) = continuous_customers / total_connected * 100 (utility_ops, monthly)
C4) Service complaints resolution efficiency % (↑) = complaints_resolved / complaints_received * 100 (crm, monthly)
C5) Complaints turnaround time (↓) = avg_days_to_resolve (crm, monthly)
C6) Sewer blockages rate (↓) = blockages / 100_km (or per 1000 connections) (utility_ops, monthly)
C7) Consumption per capita (l/c/d) (neutral/target) = total_water_sold / population_served * 1000 / 30 (billing, monthly)

Mock Data (minimal):
service_quality.json
{
  "months":["2025-01","2025-02","2025-03"],
  "dwq_pct":[96,95,97],
  "hours":[20.5,21.2,20.8],
  "pct_24x7":[28,29,30],
  "complaints":{"received":[320,340,310],"resolved":[288,305,295],"median_days":[3.4,3.1,3.0]},
  "blockages_per_100km":[16,14,13],
  "lcd":[98,102,99]
}

===============================================================================
SCENE 4 — Financial Health (Viability & efficiency)
===============================================================================
Purpose: Track revenue vs cost, NRW, staff metrics, metering, treatment utilization, pro-poor and budget variance.
Layout:
- Row 1: Combo chart: revenue vs opex (bars) with Operating Cost Coverage % (line).
- Row 2: Dual line: NRW % and Collection Efficiency %. Tiles: Staff efficiency, % Staff cost, % Metered connections.
- Row 3: Bars: Utilisation of treatment capacity (WTP, STP, FSTP). Table: Pro-poor financing %, Budget variance, Utility budget variance (abs and %).

KPIs Introduced:
Finance Core:
F1) Revenue collection efficiency % (↑) = revenue_collected / revenue_billed * 100 (finance, monthly)
F2) Operating cost coverage % (↑) = revenue / opex * 100 (finance, monthly)
F3) Non-Revenue Water % (↓) = (produced - billed)/produced * 100 (ops+billing, monthly)
F4) Working Ratio (↓) = opex / revenue (finance, monthly)
HR/Staffing:
F5) Staff efficiency (↓) = staff / 1000_connections  (ops/hr, monthly/quarter)
F6) % Staff cost (↓) = staff_cost / opex * 100 (finance, monthly)
Metering:
F7) % Metered connections (↑) = active_metered / active_connections * 100 (ops, monthly)
Treatment Utilisation:
F8) % Utilisation of WTP (↑) = utilised_wtp_capacity / design_wtp_capacity * 100 (ops, monthly)
F9) % Utilisation of STP (↑) = utilised_stp_capacity / design_stp_capacity * 100 (ops, monthly)
F10) % Utilisation of FSTP (↑) = utilised_fstp_capacity / design_fstp_capacity * 100 (ops, monthly)
Pro-poor & Budgeting:
F11) Pro-poor financing % (↑) = population_covered_by_tariff_support / total_population_served * 100 (finance/policy, annual/quarter)
F12) Utility budget variance (two ways):
   a) Allocated – Actual (absolute, ↓ good absolute gap)
   b) Actual / Allocated * 100 (↑ good if close to 100) (finance, monthly/quarter)

Mock Data (minimal):
finance.json
{
  "months":["2025-01","2025-02","2025-03"],
  "revenue":[120,115,118],
  "billed":[130,128,126],
  "opex":[100,103,101],
  "produced_m3":[155,160,158],
  "billed_m3":[110,115,113],
  "staff": 420,
  "active_connections": 68000,
  "active_metered": 65200,
  "staff_cost": 31.2,
  "wtp":{"used_mld":84,"design_mld":100},
  "stp":{"used_mld":46,"design_mld":70},
  "fstp":{"used_tpd":62,"design_tpd":90},
  "pro_poor_pct": 18,
  "budget":{"allocated": 100, "actual": 86}
}

===============================================================================
SCENE 5 — Sanitation & Reuse Chain (City/CWIS perspective)
===============================================================================
Purpose: Introduce FS/wastewater collection, treatment, and reuse; public toilets; emptying coverage.
Layout:
- Sankey/Step bars: Containment → Emptying → Transport → Treatment → Reuse.
- KPI tiles: % FS emptied, % treated FS reused, % treated wastewater reused, % total water recycled/reused, Safely managed public toilets.

KPIs Introduced:
S1) Wastewater collected and treated % (↑) = treated / collected * 100 (ops, monthly)
S2) % total water recycled/reused (↑) = wastewater_reused / total_water_supplied * 100 (ops, monthly)  [Note: ratio between wastewater and water]
S3) % of FS emptied (↑) = households_emptied / households_non_sewered * 100 (ops, monthly/quarter)
S4) % of treated FS reused (↑) = fs_reused / fs_treated * 100 (ops, monthly)
S5) % of treated wastewater reused (↑) = ww_reused / ww_treated * 100 (ops, monthly)
S6) Safely managed public toilets % (↑) = functional_public_toilets / total_public_spaces * 100 (city, monthly)

Mock Data (minimal):
sanitation_chain.json
{
  "month":"2025-03",
  "collected_mld": 68,
  "treated_mld": 43,
  "ww_reused_mld": 12,
  "fs_treated_tpd": 120,
  "fs_reused_tpd": 34,
  "households_non_sewered": 48000,
  "households_emptied": 16400,
  "public_toilets_functional_pct": 74
}

===============================================================================
SCENE 6 — Governance & Compliance (Licensing, providers, inspections, HR)
===============================================================================
Purpose: Track regulatory compliance, provider activity, inspections, and human capital.
Layout:
- Compliance Matrix: license validity, tariff validity, levy, reporting.
- Provider Activity cards: % Active Service Providers, % Active Licensed Service Providers.
- Inspections counter: Registered WTPs inspected & recertified.
- HR tiles: % Investment in human capital, Staff trained (M/F), Total staff numbers.

KPIs Introduced:
G1) % Active Service Providers (↑) = active_providers / total_providers * 100
G2) % Active licensed Service Providers (↑) = active_licensed / total_licensed * 100
G3) Total Registered WTPs inspected and recertified (↑) = count_inspected (count)
G4) % Investment in human capital (↑) = capacity_building_budget / total_WASH_budget * 100
G5) Staff trained (M/F) (neutral) = counts by gender
G6) Total staff numbers (neutral) = headcount
Additional compliance flags (Y/N): license_valid, tariff_valid, levy_paid, reporting_on_time.

Mock Data (minimal):
governance.json
{
  "active_providers": 42,
  "total_providers": 50,
  "active_licensed": 36,
  "total_licensed": 40,
  "wtp_inspected_count": 18,
  "invest_in_hc_pct": 2.6,
  "trained":{"male":120,"female":86},
  "staff_total": 512,
  "compliance":{"license":true,"tariff":true,"levy":false,"reporting":true}
}

===============================================================================
SCENE 7 — Sector & Environment (National/SDG/AMCOW layer)
===============================================================================
Purpose: Separate national/sector KPIs from utility performance; context for planners.
Layout:
- Budget bars: % National budget allocated to water/sanitation; % disbursed to WASH.
- Environment tiles: Level of water stress, Water use efficiency across sectors, Direct economic loss from water-related disasters.

KPIs Introduced:
N1) % National budget allocated to water (↑) = water_budget / total_budget * 100
N2) % National budget allocated to sanitation (↑) = sanitation_budget / total_budget * 100
N3) % of national budget disbursed to WASH (↑) = wash_disbursed / wash_allocated * 100
N4) Level of water stress (↓) = total_withdrawals / renewable_resources * 100
N5) Water use efficiency across sectors (↑) = sector_output_value / sector_water_use (e.g., agriculture, manufacturing)
N6) Direct economic loss from water-related disasters (↓) = monetary_loss (annual, currency)

Mock Data (minimal):
sector_environment.json
{
  "year": 2024,
  "budget":{"water_pct":1.9,"sanitation_pct":1.1,"wash_disbursed_pct":72},
  "water_stress_pct": 54,
  "water_use_efficiency":{"agri_usd_per_m3": 1.8, "manufacturing_usd_per_m3": 14.2},
  "disaster_loss_usd_m": 63.5
}

===============================================================================
KPI Index → Scene Mapping (for quick reference)
===============================================================================
Access ladders (surface, unimproved, limited, basic, safely water): Scene 2
Sanitation ladders (open def, unimproved, limited, basic, safely): Scene 2
% water supply coverage; % increase (water, piped); % sewered; % increase sewered: Scene 2
NRW, DWQ, Continuity, 24x7, Consumption l/c/d, Complaints resolution, Turnaround, Blockages: Scene 3
Collection efficiency, O&M coverage, Working ratio, Staff efficiency, % Staff cost, % Metered, Treatment utilisation (WTP/STP/FSTP), Pro-poor, Budget variance: Scene 4
Wastewater collected & treated, % total water recycled/reused, % FS emptied, % treated FS reused, % treated WW reused, Safely managed public toilets: Scene 5
% Active Service Providers, % Active Licensed Service Providers, WTPs inspected, % Investment in human capital, Staff trained (M/F), Total staff numbers (+ compliance flags): Scene 6
% National budget (water, sanitation), % budget disbursed to WASH, Water stress, Water use efficiency across sectors, Disaster loss: Scene 7
Asset Health Index: Scene 1 (and optional detail in Governance via Asset Register)

Notes for Developers
--------------------
- All formulas should be computed in selector hooks (e.g., useMemo) from raw measures to keep inputs auditable.
- Units and denominators must be displayed in tooltips/footers for transparency.
- For “rate per 100km” vs “per 1000 connections”, expose a toggle (defaults to /100km).
- Add DataQualityBadge (complete/partial/missing) per chart based on presence of required numerators & denominators.
- Export to PDF should respect active filters (zone/date) and include a formula legend page.

File/Module Pointers (suggested)
--------------------------------
/data/executive_summary.json
/data/access_coverage.json
/data/service_quality.json
/data/finance.json
/data/sanitation_chain.json
/data/governance.json
/data/sector_environment.json

End of Spec