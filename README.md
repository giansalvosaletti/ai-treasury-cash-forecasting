# AI Treasury Cash Forecasting Tool

**A Python-based Treasury application for cash flow forecasting, liquidity monitoring and funding management.**

## Overview

The AI Treasury Cash Forecasting Tool is a personal FinTech project designed to improve cash visibility and support short-term liquidity management through automated financial forecasting.

The application combines Treasury business logic, structured financial datasets and an interactive dashboard to project cash positions, identify potential liquidity shortfalls and support funding decisions.

The project focuses on translating practical Treasury requirements into a technology-driven forecasting solution.

## Key Features

- **Cash Flow Forecasting:** Daily projections of expected cash movements and closing balances.
- **Liquidity Monitoring:** Visibility over projected cash positions and liquidity buffers.
- **Funding Management:** Identification of potential funding shortfalls and consideration of internal and external funding inflows.
- **Multi-Currency Forecasting:** FX conversion and consolidated cash visibility.
- **Adjusted Cash Position:** Separate views of forecast closing cash and funding-adjusted cash positions.
- **Input Management:** Structured management of accounts, entities, opening balances, cash flows and FX rates.
- **Interactive Dashboard:** Financial information presented through a Streamlit interface.

## Forecasting Methodology

The forecasting engine processes opening balances and projected cash movements to calculate future liquidity positions.

The core forecasting logic considers:

- Opening cash balances
- Expected inflows and outflows
- Internal and external funding movements
- Foreign exchange conversion
- Liquidity buffer requirements

The objective is to provide both a baseline forecast and an adjusted view reflecting relevant funding movements.

## Technology Stack

- Python
- Streamlit
- Pandas
- Git / GitHub
- AI-assisted development

## Project Structure

```text
ai-treasury-cash-forecasting/
│
├── app.py
│
├── pages/
│   └── 2_Input_Management.py
│
├── src/
│   ├── forecast.py
│   └── generate_data.py
│
├── data_test/
│   ├── accounts.csv
│   ├── cash_flows.csv
│   ├── entities.csv
│   ├── fx_rates.csv
│   ├── liquidity_buffers.csv
│   └── opening_balances.csv
│
├── requirements.txt
├── .gitignore
└── README.md
```

## Installation and Setup

Clone the repository:

```bash
git clone https://github.com/giansalvosaletti/ai-treasury-cash-forecasting.git

cd ai-treasury-cash-forecasting
```

Create a virtual environment:

```bash
python3 -m venv .venv

source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

## Data and Disclaimer

This project uses synthetic financial datasets created exclusively for development and demonstration purposes.

It is an independent personal project and is not affiliated with, endorsed by or representative of any financial institution.

No confidential banking, client or proprietary institutional data is used.

## Future Development

Potential enhancements include:

- AI-assisted cash flow analysis and anomaly detection.
- Automated liquidity risk alerts.
- Scenario analysis and stress testing.
- Enhanced funding optimization.
- Integration with external financial data sources.
- Advanced forecasting models using machine learning.

## Author

**Giansalvo Saletti**

Treasury & Private Capital Professional | FinTech & AI Enthusiast

GitHub: [@giansalvosaletti](https://github.com/giansalvosaletti)
