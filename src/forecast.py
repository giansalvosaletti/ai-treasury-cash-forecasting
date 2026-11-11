from pathlib import Path
import pandas as pd

# --------------------------------------------------
# BUSINESS DAY CALENDAR
# --------------------------------------------------

def previous_business_day(date):
    """
    Return the previous business day.
    Saturday and Sunday are treated as non-business days.
    """

    date = pd.Timestamp(date) - pd.Timedelta(days=1)

    while date.weekday() >= 5:
        date -= pd.Timedelta(days=1)

    return date


# --------------------------------------------------
# 1. Percorsi dei file
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data_test"

# --------------------------------------------------
# 2. Caricamento dei dati
# --------------------------------------------------

opening_balances = pd.read_csv(DATA_DIR / "opening_balances.csv")
cash_flows = pd.read_csv(DATA_DIR / "cash_flows.csv")
liquidity_buffers = pd.read_csv(DATA_DIR / "liquidity_buffers.csv")
fx_rates = pd.read_csv(DATA_DIR / "fx_rates.csv")

# Convertiamo le date in formato datetime
opening_balances["as_of_date"] = pd.to_datetime(
    opening_balances["as_of_date"]
)

cash_flows["value_date"] = pd.to_datetime(
    cash_flows["value_date"]
)

# --------------------------------------------------
# 3. Parametri del forecast
# --------------------------------------------------

forecast_horizon = 14

# --------------------------------------------------
# OUTPUT SETTINGS
# --------------------------------------------------

VERBOSE = False

def vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

# Lista in cui raccoglieremo i forecast di tutti i conti
account_forecasts = []

# --------------------------------------------------
# 4. Forecast per ogni conto
# --------------------------------------------------

for _, account in opening_balances.iterrows():

    entity_id = account["entity_id"]
    account_id = account["account_id"]
    currency = account["currency"]

    opening_balance = account["opening_balance"]
    as_of_date = account["as_of_date"]

    # Selezioniamo i cash flow del conto
    account_flows = cash_flows[
        (cash_flows["entity_id"] == entity_id)
        & (cash_flows["account_id"] == account_id)
        & (cash_flows["currency"] == currency)
    ].copy()

    # Consideriamo i flussi successivi alla data iniziale
    account_flows = account_flows[
        account_flows["value_date"] > as_of_date
    ]

    # Creiamo il calendario del forecast
    forecast_end_date = as_of_date + pd.Timedelta(
        days=forecast_horizon
    )

    forecast_dates = pd.date_range(
        start=as_of_date,
        end=forecast_end_date,
        freq="D"
    )

    # Sommiamo i flussi per data
    daily_flows = account_flows.groupby(
        "value_date"
    )["amount"].sum()

    # Creiamo la tabella del forecast
    forecast = pd.DataFrame(index=forecast_dates)

    forecast.index.name = "date"

    forecast["net_cash_flow"] = daily_flows.reindex(
        forecast_dates,
        fill_value=0
    )

    # Saldo iniziale
    forecast["closing_balance"] = opening_balance

    # Saldi progressivi dopo la data iniziale
    forecast.loc[
        forecast.index > as_of_date,
        "closing_balance"
    ] = (
        opening_balance
        + forecast.loc[
            forecast.index > as_of_date,
            "net_cash_flow"
        ].cumsum()
    )

    # Aggiungiamo le informazioni del conto
    forecast["entity_id"] = entity_id
    forecast["account_id"] = account_id
    forecast["currency"] = currency

    account_forecasts.append(forecast)


# --------------------------------------------------
# 5. Uniamo i forecast di tutti i conti
# --------------------------------------------------

all_accounts_forecast = pd.concat(account_forecasts)

all_accounts_forecast = all_accounts_forecast.reset_index()

# --------------------------------------------------
# 6. Aggregazione per entità e valuta
# --------------------------------------------------

entity_currency_forecast = (
    all_accounts_forecast
    .groupby(
        ["date", "entity_id", "currency"],
        as_index=False
    )
    .agg(
        net_cash_flow=("net_cash_flow", "sum"),
        closing_balance=("closing_balance", "sum")
    )
)

# --------------------------------------------------
# 7. Aggiungiamo i liquidity buffer
# --------------------------------------------------

entity_currency_forecast = entity_currency_forecast.merge(
    liquidity_buffers[
        [
            "entity_id",
            "currency",
            "minimum_buffer",
            "target_buffer"
        ]
    ],
    on=["entity_id", "currency"],
    how="left"
)

# Controlliamo che ogni entità/valuta abbia entrambi i buffer
if (
    entity_currency_forecast["minimum_buffer"].isna().any()
    or entity_currency_forecast["target_buffer"].isna().any()
):
    raise ValueError(
        "Liquidity buffer mancante per una o più entità/valute."
    )


# --------------------------------------------------
# 8. Liquidity headroom, funding requirement e breach
# --------------------------------------------------

# Headroom rispetto alla soglia critica
entity_currency_forecast["liquidity_headroom"] = (
    entity_currency_forecast["closing_balance"]
    - entity_currency_forecast["minimum_buffer"]
)

# Funding requirement rispetto al target operativo
entity_currency_forecast["funding_requirement"] = (
    entity_currency_forecast["target_buffer"]
    - entity_currency_forecast["closing_balance"]
).clip(lower=0)

# Liquidity breach rispetto al minimum buffer
entity_currency_forecast["liquidity_breach"] = (
    entity_currency_forecast["minimum_buffer"]
    - entity_currency_forecast["closing_balance"]
).clip(lower=0)

# --------------------------------------------------
# 9. Conversione in reporting currency EUR
# --------------------------------------------------

REPORTING_CURRENCY = "EUR"


def get_fx_rate(currency, reporting_currency):
    """
    Restituisce il tasso per convertire una valuta
    nella reporting currency.
    """

    # Nessuna conversione necessaria
    if currency == reporting_currency:
        return 1.0

    # Cerchiamo il tasso diretto:
    # 1 unità della valuta = X unità della reporting currency
    direct_rate = fx_rates[
        (fx_rates["base_currency"] == currency)
        & (
            fx_rates["quote_currency"]
            == reporting_currency
        )
    ]

    if not direct_rate.empty:
        return direct_rate.iloc[0]["rate"]

    # Se il tasso è quotato nella direzione opposta,
    # lo invertiamo
    inverse_rate = fx_rates[
        (
            fx_rates["base_currency"]
            == reporting_currency
        )
        & (fx_rates["quote_currency"] == currency)
    ]

    if not inverse_rate.empty:
        return 1 / inverse_rate.iloc[0]["rate"]

    raise ValueError(
        f"Tasso FX non trovato per {currency} -> "
        f"{reporting_currency}"
    )


# Aggiungiamo il tasso FX a ogni riga
entity_currency_forecast["fx_rate_to_eur"] = (
    entity_currency_forecast["currency"].apply(
        lambda currency: get_fx_rate(
            currency,
            REPORTING_CURRENCY
        )
    )
)

# Convertiamo i valori nella reporting currency
entity_currency_forecast["closing_balance_eur"] = (
    entity_currency_forecast["closing_balance"]
    * entity_currency_forecast["fx_rate_to_eur"]
)

entity_currency_forecast["net_cash_flow_eur"] = (
    entity_currency_forecast["net_cash_flow"]
    * entity_currency_forecast["fx_rate_to_eur"]
)

entity_currency_forecast["minimum_buffer_eur"] = (
    entity_currency_forecast["minimum_buffer"]
    * entity_currency_forecast["fx_rate_to_eur"]
)

entity_currency_forecast["target_buffer_eur"] = (
    entity_currency_forecast["target_buffer"]
    * entity_currency_forecast["fx_rate_to_eur"]
)

entity_currency_forecast["liquidity_breach_eur"] = (
    entity_currency_forecast["liquidity_breach"]
    * entity_currency_forecast["fx_rate_to_eur"]
)

entity_currency_forecast["funding_requirement_eur"] = (
    entity_currency_forecast["funding_requirement"]
    * entity_currency_forecast["fx_rate_to_eur"]
)

# --------------------------------------------------
# 10. Consolidated Group Liquidity in EUR
# --------------------------------------------------

# Vista consolidata per data
group_forecast = (
    entity_currency_forecast
    .groupby("date", as_index=False)
    .agg(
        group_cash_eur=("closing_balance_eur", "sum"),
        group_net_cash_flow_eur=("net_cash_flow_eur", "sum"),
        group_minimum_buffer_eur=("minimum_buffer_eur", "sum"),
        gross_funding_requirement_eur=(
            "funding_requirement_eur",
            "sum"
        )
    )
)

# Headroom consolidato del gruppo
group_forecast["group_liquidity_headroom_eur"] = (
    group_forecast["group_cash_eur"]
    - group_forecast["group_minimum_buffer_eur"]
)

# Funding requirement netto a livello di gruppo
group_forecast["net_group_funding_requirement_eur"] = (
    group_forecast["group_minimum_buffer_eur"]
    - group_forecast["group_cash_eur"]
).clip(lower=0)


# --------------------------------------------------
# 12. Funding Execution Simulation
# --------------------------------------------------

# Calendario iniziale: lunedì-venerdì.
# Non include ancora le festività nazionali.

entity_currency_liquidity = (
    entity_currency_forecast
    .groupby(
        ["date", "entity_id", "currency"],
        as_index=False
    )
    .agg(
        cash_balance=("closing_balance", "sum"),
        minimum_buffer=("minimum_buffer", "sum"),
        target_buffer=("target_buffer", "sum")
    )
)

# Ordinamento cronologico
entity_currency_liquidity = entity_currency_liquidity.sort_values(
    ["date", "currency", "entity_id"]
)

# Funding adjustment cumulativo.
# Tiene traccia del funding già pianificato e del suo impatto
# sui saldi futuri per ogni entità e valuta.

funding_adjustments = {}

funding_plan = []


# --------------------------------------------------
# 13. Process dates and match surplus with deficits
# --------------------------------------------------

forecast_dates = sorted(
    entity_currency_liquidity["date"].unique()
)

for forecast_date in forecast_dates:

    daily_data = entity_currency_liquidity[
        entity_currency_liquidity["date"] == forecast_date
    ].copy()

    # Analizziamo ogni valuta separatamente
    for currency in daily_data["currency"].unique():

        currency_data = daily_data[
            daily_data["currency"] == currency
        ].copy()

        # Applichiamo il funding già pianificato
        adjusted_balances = []

        for _, row in currency_data.iterrows():

            key = (row["entity_id"], currency)

            adjustment = funding_adjustments.get(key, 0)

            adjusted_balance = (
                row["cash_balance"] + adjustment
            )

            adjusted_balances.append(adjusted_balance)

        currency_data["adjusted_balance"] = adjusted_balances


        # --------------------------------------------------
        # Available lending capacity
        # --------------------------------------------------

        # Surplus above the target buffer
        surplus_above_target = (
            currency_data["adjusted_balance"]
            - currency_data["target_buffer"]
        ).clip(lower=0)

        # Maximum amount available without breaching
        # the minimum liquidity buffer
        surplus_above_minimum = (
            currency_data["adjusted_balance"]
            - currency_data["minimum_buffer"]
        ).clip(lower=0)

        # Available surplus must respect both constraints
        currency_data["available_surplus"] = (
            surplus_above_target
            .where(
                surplus_above_target <= surplus_above_minimum,
                surplus_above_minimum
            )
        )


        # Funding requirement rispetto al target
        currency_data["funding_requirement"] = (
            currency_data["target_buffer"]
            - currency_data["adjusted_balance"]
        ).clip(lower=0)

        surplus_list = []

        for _, row in currency_data.iterrows():

            if row["available_surplus"] > 0:

                surplus_list.append({
                    "entity_id": row["entity_id"],
                    "available_surplus": row["available_surplus"]
                })

        deficit_list = []

        for _, row in currency_data.iterrows():

            if row["funding_requirement"] > 0:

                deficit_list.append({
                    "entity_id": row["entity_id"],
                    "funding_need": row["funding_requirement"]
                })

        # --------------------------------------------------
        # Funding dates
        # --------------------------------------------------
        
        # Date when the liquidity need is identified
        liquidity_need_date = pd.Timestamp(forecast_date)
        
        # Funds must arrive one business day before the liquidity need
        value_date = previous_business_day(liquidity_need_date)
        
        # Funding request must be sent one business day before value date
        action_date = previous_business_day(value_date)

        # --------------------------------------------------
        # Internal funding first
        # --------------------------------------------------

        for deficit in deficit_list:

            borrower = deficit["entity_id"]

            remaining_need = deficit["funding_need"]

            for surplus in surplus_list:

                if remaining_need <= 0:
                    break

                lender = surplus["entity_id"]

                # Un'entità non può finanziare sé stessa
                if lender == borrower:
                    continue

                available_surplus = surplus["available_surplus"]

                if available_surplus <= 0:
                    continue

                transfer_amount = min(
                    remaining_need,
                    available_surplus
                )

                # Registriamo l'azione intercompany
                funding_plan.append({
                    "action_date": action_date,
                    "value_date": value_date,
                    "liquidity_need_date": liquidity_need_date,
                    "currency": currency,
                    "lender_entity": lender,
                    "borrower_entity": borrower,
                    "funding_type": "INTERCOMPANY",
                    "funding_amount": transfer_amount,
                    "status": "PLANNED"
                })

                # Il lender perde liquidità dal value date in avanti
                lender_key = (lender, currency)

                funding_adjustments[lender_key] = (
                    funding_adjustments.get(lender_key, 0)
                    - transfer_amount
                )

                # Il borrower riceve liquidità dal value date in avanti
                borrower_key = (borrower, currency)

                funding_adjustments[borrower_key] = (
                    funding_adjustments.get(borrower_key, 0)
                    + transfer_amount
                )

                # Aggiorniamo i surplus e deficit residui
                surplus["available_surplus"] -= transfer_amount

                remaining_need -= transfer_amount

            # --------------------------------------------------
            # External funding for residual need
            # --------------------------------------------------

            if remaining_need > 0:

                funding_plan.append({
                    "action_date": action_date,
                    "value_date": value_date,
                    "liquidity_need_date": liquidity_need_date,
                    "currency": currency,
                    "lender_entity": "EXTERNAL",
                    "borrower_entity": borrower,
                    "funding_type": "EXTERNAL",
                    "funding_amount": remaining_need,
                    "status": "PLANNED"
                })

                borrower_key = (borrower, currency)

                funding_adjustments[borrower_key] = (
                    funding_adjustments.get(borrower_key, 0)
                    + remaining_need
                )


# --------------------------------------------------
# 14. Output of the funding plan
# --------------------------------------------------

funding_plan_df = pd.DataFrame(funding_plan)

# --------------------------------------------------
# Funding timing feasibility check
# --------------------------------------------------

vprint("\n--- FUNDING TIMING FEASIBILITY CHECK ---")

if funding_plan_df.empty:

    vprint("No funding actions to validate.")

else:

    # Convert funding dates to datetime
    funding_plan_df["action_date"] = pd.to_datetime(
        funding_plan_df["action_date"]
    )

    funding_plan_df["value_date"] = pd.to_datetime(
        funding_plan_df["value_date"]
    )

    funding_plan_df["liquidity_need_date"] = pd.to_datetime(
        funding_plan_df["liquidity_need_date"]
    )

    # Check that funding is available before the liquidity need
    funding_plan_df["timing_feasible"] = (
        funding_plan_df["value_date"]
        <= funding_plan_df["liquidity_need_date"]
    )

    # Check that the funding request is not after the value date
    funding_plan_df["request_timing_feasible"] = (
        funding_plan_df["action_date"]
        <= funding_plan_df["value_date"]
    )

    # Overall timing validation
    funding_plan_df["timing_status"] = (
        funding_plan_df["timing_feasible"]
        & funding_plan_df["request_timing_feasible"]
    ).map({
        True: "FEASIBLE",
        False: "NOT FEASIBLE"
    })

    vprint(
        funding_plan_df[
            [
                "action_date",
                "value_date",
                "liquidity_need_date",
                "currency",
                "funding_type",
                "funding_amount",
                "timing_status"
            ]
        ].to_string(index=False)
    )

vprint("\n--- FUNDING PLAN BY CURRENCY ---")

if funding_plan_df.empty:

    vprint("No funding transfers required.")

else:

    vprint(
        funding_plan_df[
            [
                "action_date",
                "value_date",
                "liquidity_need_date",
                "currency",
                "lender_entity",
                "borrower_entity",
                "funding_type",
                "funding_amount",
                "status"
            ]
        ].to_string(index=False)
    )

# --------------------------------------------------
# 15. Adjusted Liquidity Forecast
# --------------------------------------------------

vprint("\n--- ADJUSTED LIQUIDITY FORECAST ---")

# Creiamo una lista con l'impatto di ogni funding action
funding_impacts = []

if not funding_plan_df.empty:

    for _, action in funding_plan_df.iterrows():

        currency = action["currency"]
        value_date = pd.Timestamp(action["value_date"])

        lender = action["lender_entity"]
        borrower = action["borrower_entity"]

        amount = action["funding_amount"]

        # Impatto positivo per chi riceve il funding
        funding_impacts.append({
            "date": value_date,
            "entity_id": borrower,
            "currency": currency,
            "funding_adjustment": amount
        })

        # Impatto negativo per chi trasferisce la liquidità
        if action["funding_type"] == "INTERCOMPANY":

            funding_impacts.append({
                "date": value_date,
                "entity_id": lender,
                "currency": currency,
                "funding_adjustment": -amount
            })


# Se esistono funding actions, calcoliamo l'impatto cumulativo
if funding_impacts:

    funding_impacts_df = pd.DataFrame(funding_impacts)

    # Sommiamo le azioni che hanno la stessa data,
    # entità e valuta
    funding_impacts_df = (
        funding_impacts_df
        .groupby(
            ["date", "entity_id", "currency"],
            as_index=False
        )
        .agg(
            funding_adjustment=("funding_adjustment", "sum")
        )
    )

else:

    # Se non ci sono funding actions,
    # l'impatto del funding è zero
    funding_impacts_df = pd.DataFrame(
        columns=[
            "date",
            "entity_id",
            "currency",
            "funding_adjustment"
        ]
    )


# --------------------------------------------------
# Merge con il forecast originale
# --------------------------------------------------

adjusted_forecast = entity_currency_forecast.merge(
    funding_impacts_df,
    on=["date", "entity_id", "currency"],
    how="left"
)

# Nessuna funding action = impatto zero
adjusted_forecast["funding_adjustment"] = (
    adjusted_forecast["funding_adjustment"]
    .fillna(0)
)

# Convert funding adjustment to numeric
adjusted_forecast["funding_adjustment"] = pd.to_numeric(
    adjusted_forecast["funding_adjustment"],
    errors="raise"
)

# --------------------------------------------------
# Cumulative funding adjustment
# --------------------------------------------------

adjusted_forecast = adjusted_forecast.sort_values(
    ["entity_id", "currency", "date"]
)

adjusted_forecast["cumulative_funding_adjustment"] = (
    adjusted_forecast
    .groupby(["entity_id", "currency"])["funding_adjustment"]
    .cumsum()
)


# --------------------------------------------------
# Adjusted closing balance
# --------------------------------------------------

adjusted_forecast["adjusted_balance"] = (
    adjusted_forecast["closing_balance"]
    + adjusted_forecast["cumulative_funding_adjustment"]
)


# --------------------------------------------------
# 16. Minimum Buffer Validation
# --------------------------------------------------

adjusted_forecast["minimum_buffer_gap"] = (
    adjusted_forecast["adjusted_balance"]
    - adjusted_forecast["minimum_buffer"]
)

adjusted_forecast["minimum_buffer_status"] = (
    adjusted_forecast["minimum_buffer_gap"]
    .apply(lambda x: "BUFFER OK" if x >= 0 else "BUFFER BREACH")
)

minimum_buffer_check = adjusted_forecast[
    [
        "date",
        "entity_id",
        "currency",
        "adjusted_balance",
        "minimum_buffer",
        "minimum_buffer_gap",
        "minimum_buffer_status"
    ]
].copy()

buffer_breaches = minimum_buffer_check[
    minimum_buffer_check["minimum_buffer_status"] == "BUFFER BREACH"
]

if not buffer_breaches.empty:
    print("\n--- WARNING: MINIMUM BUFFER BREACHES ---")
    print(buffer_breaches.to_string(index=False))
else:
    print("\nMinimum buffer validation: ALL CHECKS PASSED")


# Temporary diagnostic for E003 USD
vprint("\n--- E003 USD FUNDING DIAGNOSTIC ---")

vprint(
    adjusted_forecast[
        (
            adjusted_forecast["entity_id"] == "E003"
        )
        &
        (
            adjusted_forecast["currency"] == "USD"
        )
    ][
        [
            "date",
            "closing_balance",
            "funding_adjustment",
            "cumulative_funding_adjustment",
            "adjusted_balance",
            "target_buffer"
        ]
    ].to_string(index=False)
)

# --------------------------------------------------
# Adjusted liquidity indicators
# --------------------------------------------------

adjusted_forecast["adjusted_funding_requirement"] = (
    adjusted_forecast["target_buffer"]
    - adjusted_forecast["adjusted_balance"]
).clip(lower=0)

adjusted_forecast["adjusted_liquidity_breach"] = (
    adjusted_forecast["minimum_buffer"]
    - adjusted_forecast["adjusted_balance"]
).clip(lower=0)

# --------------------------------------------------
# Intercompany borrower funding validation
# --------------------------------------------------

vprint("\n--- INTERCOMPANY BORROWER FUNDING CHECK ---")

if funding_plan_df.empty:

    vprint("No funding actions to validate.")

else:

    borrower_funding = funding_plan_df[
        funding_plan_df["funding_type"] == "INTERCOMPANY"
    ].copy()

    if borrower_funding.empty:

        vprint("No intercompany borrower funding actions.")

    else:

        borrower_checks = []

        for _, action in borrower_funding.iterrows():

            liquidity_need_date = pd.Timestamp(
                action["liquidity_need_date"]
            )
            borrower = action["borrower_entity"]
            currency = action["currency"]
            amount = action["funding_amount"]

            borrower_position = adjusted_forecast[
                (
                    adjusted_forecast["date"]
                    == liquidity_need_date
                )
                &
                (
                    adjusted_forecast["entity_id"]
                    == borrower
                )
                &
                (
                    adjusted_forecast["currency"]
                    == currency
                )
            ]

            if borrower_position.empty:

                adjusted_balance = None
                target_buffer = None
                funding_status = "POSITION NOT FOUND"

            else:

                adjusted_balance = borrower_position.iloc[0][
                    "adjusted_balance"
                ]

                target_buffer = borrower_position.iloc[0][
                    "target_buffer"
                ]

                if adjusted_balance >= target_buffer:

                    funding_status = "TARGET MET"

                else:

                    funding_status = "TARGET NOT MET"

            borrower_checks.append({
                "liquidity_need_date": liquidity_need_date,
                "borrower_entity": borrower,
                "currency": currency,
                "funding_amount": amount,
                "adjusted_balance": adjusted_balance,
                "target_buffer": target_buffer,
                "funding_status": funding_status
            })

        borrower_checks_df = pd.DataFrame(borrower_checks)
        
        vprint(
            borrower_checks_df[
                [
                    "liquidity_need_date",
                    "borrower_entity",
                    "currency",
                    "funding_amount",
                    "adjusted_balance",
                    "target_buffer",
                    "funding_status"
                ]
            ].to_string(index=False)
        )
# --------------------------------------------------
# Intercompany lender buffer validation
# --------------------------------------------------

vprint("\n--- INTERCOMPANY LENDER BUFFER CHECK ---")

if funding_plan_df.empty:

    vprint("No funding actions to validate.")

else:

    intercompany_funding = funding_plan_df[
        funding_plan_df["funding_type"] == "INTERCOMPANY"
    ].copy()

    if intercompany_funding.empty:

        vprint("No intercompany funding actions.")

    else:

        lender_checks = []

        for _, action in intercompany_funding.iterrows():

            value_date = pd.Timestamp(action["value_date"])
            lender = action["lender_entity"]
            currency = action["currency"]
            amount = action["funding_amount"]

            # Find the lender's adjusted balance on the funding value date
            lender_position = adjusted_forecast[
                (
                    adjusted_forecast["date"]
                    == value_date
                )
                &
                (
                    adjusted_forecast["entity_id"]
                    == lender
                )
                &
                (
                    adjusted_forecast["currency"]
                    == currency
                )
            ]

            if lender_position.empty:

                lender_checks.append({
                    "value_date": value_date,
                    "lender_entity": lender,
                    "currency": currency,
                    "funding_amount": amount,
                    "adjusted_balance": None,
                    "minimum_buffer": None,
                    "buffer_status": "POSITION NOT FOUND"
                })

            else:

                lender_balance = lender_position.iloc[0][
                    "adjusted_balance"
                ]

                minimum_buffer = lender_position.iloc[0][
                    "minimum_buffer"
                ]

                # Calculate remaining lending capacity
                lending_capacity = max(
                    lender_balance - minimum_buffer,
                    0
                )

                if lender_balance >= minimum_buffer:

                    buffer_status = "BUFFER OK"

                else:

                    buffer_status = "BUFFER BREACH"


                lender_checks.append({
                    "value_date": value_date,
                    "lender_entity": lender,
                    "currency": currency,
                    "funding_amount": amount,
                    "adjusted_balance": lender_balance,
                    "minimum_buffer": minimum_buffer,
                    "lending_capacity": lending_capacity,
                    "buffer_status": buffer_status
                })

        lender_checks_df = pd.DataFrame(lender_checks)

        vprint(
            lender_checks_df.to_string(index=False)
        )

# --------------------------------------------------
# Output
# --------------------------------------------------

columns_to_display = [
    "date",
    "entity_id",
    "currency",
    "closing_balance",
    "funding_adjustment",
    "cumulative_funding_adjustment",
    "adjusted_balance",
    "target_buffer",
    "minimum_buffer",
    "adjusted_funding_requirement",
    "adjusted_liquidity_breach"
]

vprint(
    adjusted_forecast[
        columns_to_display
    ].to_string(index=False)
)

# ============================================================
# 17 - EXECUTIVE FUNDING SUMMARY
# ============================================================

print("\n--- EXECUTIVE FUNDING SUMMARY ---")

if not funding_plan_df.empty:

    # Summary of funding by type and currency
    funding_summary = (
        funding_plan_df
        .groupby(
            ["funding_type", "currency"],
            as_index=False
        )
        .agg(
            total_funding=("funding_amount", "sum"),
            number_of_transactions=("funding_amount", "count")
        )
    )

    print("\nFunding by type and currency:")
    print(funding_summary.to_string(index=False))

    # Detailed list of funding decisions
    funding_decisions = funding_plan_df[
        [
            "action_date",
            "value_date",
            "liquidity_need_date",
            "currency",
            "lender_entity",
            "borrower_entity",
            "funding_type",
            "funding_amount",
            "status"
        ]
    ].copy()

    print("\nFunding decisions:")
    print(funding_decisions.to_string(index=False))

    # Total planned funding by currency
    planned_funding_by_currency = (
        funding_plan_df
        .groupby("currency")["funding_amount"]
        .sum()
    )

    print("\nKey metrics:")

    for currency, amount in planned_funding_by_currency.items():
        print(f"Planned funding {currency}: {amount:,.2f}")

else:
    print("No funding actions required.")

    
# ============================================================
# 17 - EXPORT OUTPUTS TO CSV
# ============================================================

from pathlib import Path

# Create output folder if it does not exist
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

# Export funding plan
funding_plan_df.to_csv(
    output_dir / "funding_plan.csv",
    index=False
)

# Export adjusted liquidity forecast
adjusted_forecast.to_csv(
    output_dir / "adjusted_liquidity_forecast.csv",
    index=False
)

# Export funding summary
if funding_plan_df.empty:
    funding_summary = pd.DataFrame(
        columns=[
            "funding_type",
            "currency",
            "total_funding",
            "number_of_transactions"
        ]
    )
else:
    funding_summary = (
        funding_plan_df
        .groupby(
            ["funding_type", "currency"],
            as_index=False
        )
        .agg(
            total_funding=("funding_amount", "sum"),
            number_of_transactions=("funding_amount", "count")
        )
    )

funding_summary.to_csv(
    output_dir / "funding_summary.csv",
    index=False
)

print("\n--- CSV EXPORT COMPLETED ---")
print("Files saved in the outputs folder:")
print("- funding_plan.csv")
print("- adjusted_liquidity_forecast.csv")
print("- funding_summary.csv")