# Water Utility Performance Dashboard - User Manual

## 📘 Introduction
This document provides a detailed guide to the metrics and visualizations presented in the Water Utility Performance Dashboard. It is intended to help stakeholders understand how key performance indicators (KPIs) are calculated and interpreted to support data-driven decision-making.

---

## 1. Executive Dashboard (Home)
**Purpose**: Provides a high-level snapshot of utility performance across critical domains to facilitate quick assessment of overall health.

### Key Metrics

#### Service Coverage Score
A composite index (0-100) reflecting how well the population is reached.
- **Formula**: [(Water Coverage% + Sanitation Coverage%) / 2](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
  - *Water Coverage*: Average percentage of population with access to safely managed water.
  - *Sanitation Coverage*: Average percentage of population with access to safely managed sanitation.
- **Status Thresholds**:
  - 🟢 **Good**: > 80%
  - 🟡 **Warning**: 60–80%
  - 🔴 **Critical**: < 60%

#### Financial Health Index
A weighted score indicating financial sustainability.
- **Formula**: [(Collection Efficiency * 0.4) + (Operating Coverage * 0.4) + (Budget Utilization * 0.2)](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
- **Components**:
  - *Collection Efficiency*: [(Total Paid / Total Billed) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169) (Capped at 100%)
  - *Operating Coverage*: [(Total Revenue / Total Opex) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169) (Capped at 120%)
  - *Budget Utilization*: [(Total Opex / Total Allocated Budget) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169) (Capped at 100%)

#### Operational Efficiency Score
A measure of technical performance and system reliability.
- **Formula**: [((100 - NRW%) + Capacity Utilization% + (Service Hours/24 * 100)) / 3](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
- **Components**:
  - *NRW (Non-Revenue Water)*: [((Production - Billing Consumption) / Production) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
  - *Capacity Utilization*: [(Wastewater Treated / Plant Capacity) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
  - *Service Hours*: Average daily hours of supply (normalized to 100 scale).

#### Service Quality Index
An average of customer satisfaction and compliance metrics.
- **Formula**: [(Water Quality Compliance% + Complaint Resolution Rate% + Asset Health Score) / 3](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
- **Components**:
  - *Water Quality Compliance*: Percentage of water samples passing standards.
  - *Complaint Resolution*: Percentage of registered complaints marked as resolved.
  - *Asset Health*: Aggregated score of infrastructure condition.

---

## 2. Access & Coverage
**Purpose**: Monitors the expansion of water and sanitation services towards universal access goals (SDG 6).

### Key Metrics
- **Population Served**: Total population with valid connections.
- **Safely Managed Access**: Population using improved sources located on premises, available when needed, and free from contamination.
- **Access Ladder**: Classification of population into JMP categories (Safely Managed, Basic, Limited, Unimproved, Open Defecation).

---

## 3. Service Quality & Reliability
**Purpose**: Tracks the consistency, safety, and responsiveness of service delivery.

### Key Metrics
- **Water Quality Compliance**:
  - *Chlorine Residual*: `% of tests passing chlorine standards`
  - *E. coli*: `% of tests free from E. coli`
  - **Formula**: [(Tests Passed / Total Tests Conducted) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
- **Service Continuity**: Average hours of water supply per day per zone.
- **Complaint Resolution Rate**: [(Complaints Resolved / Total Complaints Received) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
- **Response Time**: Average time taken to resolve technical complaints.

---

## 4. Financial Health
**Purpose**: Analyzes revenue generation, cost recovery, and budget execution.

### Key Metrics
- **Total Budget**: Total funding allocated for the period.
- **Total Billed**: Total value of invoices issued to customers.
- **Revenue Collected**: Total actual payments received.
- **Collection Rate**: [(Revenue Collected / Total Billed) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
  - *Target*: > 85%
- **Outstanding Debt**: `Total Billed - Revenue Collected` (Cumulative unpaid invoices).
- **Cost Recovery Ratio**: [(Total Revenue / Operational Expenses) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
  - Indicates if the utility can cover its running costs from its own revenue.
- **Revenue per Staff**: `Total Revenue / Total Staff Count` (Efficiency metric).

---

## 5. Production & Operations
**Purpose**: Monitors water production volumes, system efficiency, and source sustainability.

### Key Metrics
- **Total Production**: Total volume extracted/treated in cubic meters (m³).
- **Non-Revenue Water (NRW)**: Volume of water produced but not billed (lost to leaks or theft).
  - **Formula**: [(Production - Consumption) / Production](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
- **Capacity Utilization**: [(Actual Production / Estimated Design Capacity) * 100](file:///Users/akotet/Documents/Applied-Data-Institute/Dashboard/auth.py#110-169)
  - *Note*: Design capacity is estimated as `Max Observed Production * 1.1` in the absence of static asset data.
- **Active Sources**: Count of production sources (wells/plants) reporting non-zero output.

---

## 6. Sector Overview
**Purpose**: Provides high-level national context, budget allocation, and environmental factors.

### Key Metrics
- **Sector Budget Allocation**: Percentage of national budget allocated to Water vs Sanitation.
- **Water Stress**: Percentage of available water resources currently utilized.
- **Water Use Efficiency (WUE)**: Economic value generated per cubic meter of water used in Agriculture and Manufacturing (`USD/m³`).
