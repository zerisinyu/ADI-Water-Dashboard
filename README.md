# Water Utility Performance Dashboard 
By Applied Data 25', Equitech Futures

🔗 [**Demo link**](https://adi-water-dashboard.streamlit.app)

## 🌍 Overview
This repository hosts the **Water Utility Performance Dashboard**, a comprehensive suite of tools designed to monitor, analyze, and improve water and sanitation services. The platform combines secure role-based dashboards, AI-powered insights, and ad-hoc visualization tools to support decision-making at national, city, and zone levels.

It is also a capstone group project collaborated with [Athena Infonomics](https://www.athenainfonomics.com) & Africa Utility Data Collaborative (AUDC), done by Fusion 4, a team from Applied Data Institute 2025, [Equitech Futures](https://www.equitechfutures.com/programs/adi).  

## 📂 Repository Structure

| Component | Description |
|-----------|-------------|
| **[`Dashboard/`](./Dashboard)** | The core Streamlit web application. Contains source code (`src_page/`), pages, and UI logic. See [Dashboard README](./Dashboard/README.md) for usage details. |
| **`Data/`** | Central storage for input CSV/JSON datasets. Used by both the Dashboard and analysis scripts. |
| **`Outputs/`** | Generated reports, static plots, and export artifacts. |
| **`visualize.py`** | CLI utility for generating quick static Plotly visualizations without running the full dashboard. |
| **`visualize.ipynb`** | Jupyter notebook for exploratory data analysis and prototyping new visuals. |

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Virtual environment (recommended)

### Installation
1. **Clone the repository**
   ```bash
   git clone https://github.com/zerisinyu/ADI-Water-Dashboard.git
   cd ADI-Water-Dashboard
   ```

2. **Set up the environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Secrets**
   The application requires specific credentials for Authentication and AI features.
   - Copy `secrets.toml.example` to `.streamlit/secrets.toml` inside the `Dashboard/` directory:
     ```bash
     mkdir -p Dashboard/.streamlit
     cp secrets.toml.example Dashboard/.streamlit/secrets.toml
     ```
   - Edit `Dashboard/.streamlit/secrets.toml` to add your **Gemini/Grok API Keys** and define initial **User Credentials**.

### Running the Platform
To launch the main dashboard application:
```bash
streamlit run Dashboard/Home.py
```
*For detailed user guides, login credentials, and feature documentation, please refer to the [Dashboard Documentation](./Dashboard/README.md).*

## 📊 Data Management
The platform relies on specific datasets located in the `Data/` directory. Ensure the following files are present:
- **Access Data**: `Water Access Data.csv`, `Sewer Access Data.csv`
- **Operations**: `production.csv`, `Service_data.csv`
- **Finance**: `billing.csv`, `financial_services.csv`
- **Metadata**: `sector_environment.json`, `sanitation_chain.json`

## 🛠️ Development

### Branch Strategy
- `main`: Production-ready code.
- `develop`: Integration branch for ongoing work.
- `feature/*`: New features (e.g., `feature/ai-integration`).
- `bugfix/*`: Fixes for existing issues.

## 👥 Contributors
- Sadikshya
- Zhomart
- Sinyu — [@zerisinyu](https://github.com/zerisinyu)
- Akotet — [@Akotet08](https://github.com/Akotet08)
