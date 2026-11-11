
from pathlib import Path
import pandas as pd

# Cartella in cui salveremo i file CSV
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# 1. Entità del gruppo
entities = pd.DataFrame([
    {
        "entity_id": "E001",
        "entity_name": "LuxCo",
        "reporting_currency": "EUR",
        "country": "Luxembourg",
    },
    {
        "entity_id": "E002",
        "entity_name": "DubaiCo",
        "reporting_currency": "AED",
        "country": "UAE",
    },
    {
        "entity_id": "E003",
        "entity_name": "USCo",
        "reporting_currency": "USD",
        "country": "USA",
    },
])

# 2. Conti bancari
accounts = pd.DataFrame([
    {
        "account_id": "A001",
        "entity_id": "E001",
        "bank_name": "Demo Bank Europe",
        "currency": "EUR",
        "account_type": "Operating",
    },
    {
        "account_id": "A002",
        "entity_id": "E001",
        "bank_name": "Demo Bank Europe",
        "currency": "USD",
        "account_type": "Operating",
    },
    {
        "account_id": "A003",
        "entity_id": "E002",
        "bank_name": "Demo Bank UAE",
        "currency": "AED",
        "account_type": "Operating",
    },
    {
        "account_id": "A004",
        "entity_id": "E003",
        "bank_name": "Demo Bank US",
        "currency": "USD",
        "account_type": "Operating",
    },
    {
        "account_id": "A005",
        "entity_id": "E003",
        "bank_name": "Demo Bank US",
        "currency": "GBP",
        "account_type": "Operating",
    },
])

# 3. Saldi iniziali
opening_balances = pd.DataFrame([
    {
        "as_of_date": "2026-11-05",
        "entity_id": "E001",
        "account_id": "A001",
        "currency": "EUR",
        "opening_balance": 250000,
    },
    {
        "as_of_date": "2026-11-05",
        "entity_id": "E001",
        "account_id": "A002",
        "currency": "USD",
        "opening_balance": 100000,
    },
    {
        "as_of_date": "2026-11-05",
        "entity_id": "E002",
        "account_id": "A003",
        "currency": "AED",
        "opening_balance": 600000,
    },
    {
        "as_of_date": "2026-11-05",
        "entity_id": "E003",
        "account_id": "A004",
        "currency": "USD",
        "opening_balance": 180000,
    },
    {
        "as_of_date": "2026-11-05",
        "entity_id": "E003",
        "account_id": "A005",
        "currency": "GBP",
        "opening_balance": 50000,
    },
])

# 4. Flussi di cassa previsti
cash_flows = pd.DataFrame([
    {
        "flow_id": "F001",
        "entity_id": "E001",
        "account_id": "A001",
        "value_date": "2026-11-06",
        "amount": -30000,
        "currency": "EUR",
        "category": "Supplier payment",
        "status": "Committed",
        "scenario": "Base",
    },
    {
        "flow_id": "F002",
        "entity_id": "E001",
        "account_id": "A001",
        "value_date": "2026-11-07",
        "amount": 80000,
        "currency": "EUR",
        "category": "Customer receipt",
        "status": "Committed",
        "scenario": "Base",
    },
    {
        "flow_id": "F003",
        "entity_id": "E001",
        "account_id": "A001",
        "value_date": "2026-11-08",
        "amount": -250000,
        "currency": "EUR",
        "category": "Debt repayment",
        "status": "Committed",
        "scenario": "Base",
    },
    {
        "flow_id": "F004",
        "entity_id": "E001",
        "account_id": "A002",
        "value_date": "2026-11-09",
        "amount": 50000,
        "currency": "USD",
        "category": "Customer receipt",
        "status": "Forecast",
        "scenario": "Base",
    },
    {
        "flow_id": "F005",
        "entity_id": "E002",
        "account_id": "A003",
        "value_date": "2026-11-07",
        "amount": -200000,
        "currency": "AED",
        "category": "Supplier payment",
        "status": "Committed",
        "scenario": "Base",
    },
    {
        "flow_id": "F006",
        "entity_id": "E002",
        "account_id": "A003",
        "value_date": "2026-11-10",
        "amount": 100000,
        "currency": "AED",
        "category": "Customer receipt",
        "status": "Forecast",
        "scenario": "Base",
    },
    {
        "flow_id": "F007",
        "entity_id": "E003",
        "account_id": "A004",
        "value_date": "2026-11-08",
        "amount": -100000,
        "currency": "USD",
        "category": "Supplier payment",
        "status": "Committed",
        "scenario": "Base",
    },
    {
        "flow_id": "F008",
        "entity_id": "E003",
        "account_id": "A005",
        "value_date": "2026-11-11",
        "amount": 20000,
        "currency": "GBP",
        "category": "Customer receipt",
        "status": "Forecast",
        "scenario": "Base",
    },
])

# 5. Tassi FX
fx_rates = pd.DataFrame([
    {
        "rate_date": "2026-11-05",
        "base_currency": "USD",
        "quote_currency": "EUR",
        "rate": 0.92,
    },
    {
        "rate_date": "2026-11-05",
        "base_currency": "GBP",
        "quote_currency": "EUR",
        "rate": 1.15,
    },
    {
        "rate_date": "2026-11-05",
        "base_currency": "AED",
        "quote_currency": "EUR",
        "rate": 0.25,
    },
    {
        "rate_date": "2026-11-05",
        "base_currency": "USD",
        "quote_currency": "AED",
        "rate": 3.67,
    },
])

# 6. Liquidity buffers
liquidity_buffers = pd.DataFrame([
    {
        "entity_id": "E001",
        "currency": "EUR",
        "minimum_buffer": 100000,
        "effective_date": "2026-11-05",
    },
    {
        "entity_id": "E001",
        "currency": "USD",
        "minimum_buffer": 25000,
        "effective_date": "2026-11-05",
    },
    {
        "entity_id": "E002",
        "currency": "AED",
        "minimum_buffer": 150000,
        "effective_date": "2026-11-05",
    },
    {
        "entity_id": "E003",
        "currency": "USD",
        "minimum_buffer": 50000,
        "effective_date": "2026-11-05",
    },
    {
        "entity_id": "E003",
        "currency": "GBP",
        "minimum_buffer": 10000,
        "effective_date": "2026-11-05",
    },
])

# Salviamo ogni tabella in un file CSV
tables = {
    "entities.csv": entities,
    "accounts.csv": accounts,
    "opening_balances.csv": opening_balances,
    "cash_flows.csv": cash_flows,
    "fx_rates.csv": fx_rates,
    "liquidity_buffers.csv": liquidity_buffers,
}

for filename, table in tables.items():
    table.to_csv(DATA_DIR / filename, index=False)

print("Dataset creato con successo!")
print(f"File salvati in: {DATA_DIR}")
# Controlliamo il numero di righe delle tabelle
for filename, table in tables.items():
    print(filename, ":", len(table), "righe")