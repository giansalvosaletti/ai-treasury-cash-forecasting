
from pathlib import Path

import pandas as pd
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Treasury Cash Forecast",
    page_icon="💰",
    layout="wide"
)

st.title("Treasury Cash Forecasting Tool")

st.caption(
    "Multi-entity | Multi-currency | Liquidity & Funding Management"
)


# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data_test"
OUTPUT_DIR = PROJECT_DIR / "outputs"


@st.cache_data
def load_data():

    forecast = pd.read_csv(
        OUTPUT_DIR / "adjusted_liquidity_forecast.csv"
    )

    funding_plan = pd.read_csv(
        OUTPUT_DIR / "funding_plan.csv"
    )

    entities_df = pd.read_csv(DATA_DIR / "entities.csv")
    entity_name_map = dict(
        zip(entities_df["entity_id"], entities_df["entity_name"])
    )

    forecast["date"] = pd.to_datetime(
        forecast["date"]
    )

    for column in [
        "action_date",
        "value_date",
        "liquidity_need_date"
    ]:

        if column in funding_plan.columns:

            funding_plan[column] = pd.to_datetime(
                funding_plan[column]
            )

    return forecast, funding_plan, entity_name_map


try:

    forecast, funding_plan, entity_name_map = load_data()

except FileNotFoundError:

    st.error(
        "Output files not found. "
        "Please run forecast.py before launching the dashboard."
    )

    st.stop()


# --------------------------------------------------
# CURRENCY FORMATTING
# --------------------------------------------------

CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "CHF": "CHF ",
    "JPY": "¥"
}


def format_currency(amount, currency):

    symbol = CURRENCY_SYMBOLS.get(
        currency,
        f"{currency} "
    )

    return f"{symbol}{amount:,.0f}"


# --------------------------------------------------
# SIDEBAR FILTERS (PERSIST ACROSS MULTIPAGE NAVIGATION)
# --------------------------------------------------

st.sidebar.header("Filters")

entity_ids = sorted(
    forecast["entity_id"].dropna().unique().tolist()
)
entity_options = {
    entity_name_map.get(entity_id, str(entity_id)): entity_id
    for entity_id in entity_ids
}
entity_names = list(entity_options.keys())

currencies = sorted(
    forecast["currency"].dropna().unique().tolist()
)

# Keep durable values separately: Streamlit may clean up widget state
# when a widget is not rendered on another page.
if "saved_entity_filter" not in st.session_state:
    st.session_state["saved_entity_filter"] = entity_names
if "saved_currency_filter" not in st.session_state:
    st.session_state["saved_currency_filter"] = currencies

def persist_entity_filter():
    st.session_state["saved_entity_filter"] = st.session_state.get(
        "entity_filter_widget", entity_names
    )

def persist_currency_filter():
    st.session_state["saved_currency_filter"] = st.session_state.get(
        "currency_filter_widget", currencies
    )

# Recreate widget values from durable state when returning to Overview.
if "entity_filter_widget" not in st.session_state:
    st.session_state["entity_filter_widget"] = [
        name for name in st.session_state["saved_entity_filter"]
        if name in entity_names
    ]
if "currency_filter_widget" not in st.session_state:
    st.session_state["currency_filter_widget"] = [
        currency for currency in st.session_state["saved_currency_filter"]
        if currency in currencies
    ]

selected_entity_names = st.sidebar.multiselect(
    "Entity",
    options=entity_names,
    key="entity_filter_widget",
    on_change=persist_entity_filter,
)
selected_entities = [
    entity_options[name] for name in selected_entity_names
]

selected_currencies = st.sidebar.multiselect(
    "Currency",
    options=currencies,
    key="currency_filter_widget",
    on_change=persist_currency_filter,
)

# --------------------------------------------------
# FILTER FORECAST
# --------------------------------------------------

filtered_forecast = forecast[
    forecast["entity_id"].isin(selected_entities)
    & forecast["currency"].isin(selected_currencies)
].copy()


# --------------------------------------------------
# FILTER FUNDING PLAN
# --------------------------------------------------

if not funding_plan.empty:

    filtered_funding_plan = funding_plan[
        funding_plan["borrower_entity"].isin(selected_entities)
        & funding_plan["currency"].isin(selected_currencies)
    ].copy()

else:

    filtered_funding_plan = funding_plan.copy()


# --------------------------------------------------
# KPI SECTION
# --------------------------------------------------

st.header("Liquidity Overview")

if filtered_forecast.empty:

    st.warning(
        "No data available for the selected filters."
    )

else:

    # ----------------------------------------------
    # FORECAST CLOSING CASH
    # ----------------------------------------------

    latest_date = filtered_forecast["date"].max()

    latest_positions = filtered_forecast[
        filtered_forecast["date"] == latest_date
    ]

    total_cash = latest_positions[
        "closing_balance_eur"
    ].sum()

    # Adjusted closing cash includes the impact of planned
    # intercompany and external funding.
    latest_positions = latest_positions.copy()
    latest_positions["adjusted_balance_eur"] = (
        latest_positions["adjusted_balance"]
        * latest_positions["fx_rate_to_eur"]
    )
    total_adjusted_cash = latest_positions[
        "adjusted_balance_eur"
    ].sum()

    # ----------------------------------------------
    # FUNDING CONVERSION INTO EUR
    # ----------------------------------------------

    if not filtered_funding_plan.empty:

        # Latest available FX rate for each entity/currency
        fx_lookup = (
            forecast
            .sort_values("date")
            .drop_duplicates(
                subset=["entity_id", "currency"],
                keep="last"
            )
            .set_index(
                ["entity_id", "currency"]
            )["fx_rate_to_eur"]
        )

        filtered_funding_plan["fx_rate_to_eur"] = (
            filtered_funding_plan.apply(
                lambda row: fx_lookup.get(
                    (
                        row["borrower_entity"],
                        row["currency"]
                    ),
                    1.0
                ),
                axis=1
            )
        )

        filtered_funding_plan["funding_amount_eur"] = (
            filtered_funding_plan["funding_amount"]
            * filtered_funding_plan["fx_rate_to_eur"]
        )

        total_funding_eur = (
            filtered_funding_plan["funding_amount_eur"]
            .sum()
        )

    else:

        total_funding_eur = 0.0

    # ----------------------------------------------
    # LIQUIDITY BREACH DAYS
    # ----------------------------------------------

    breach_days = (
        filtered_forecast
        .groupby(
            ["entity_id", "currency", "date"]
        )["adjusted_liquidity_breach"]
        .max()
    )

    total_breaches = breach_days.sum()

    # ----------------------------------------------
    # DISPLAY KPIs
    # ----------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Forecast Closing Cash (EUR)",
        f"€ {total_cash:,.0f}",
        help=(
            "Closing cash before planned funding adjustments, "
            "converted into EUR using the forecast FX rates."
        )
    )

    col2.metric(
        "Adjusted Closing Cash (EUR)",
        f"€ {total_adjusted_cash:,.0f}",
        help=(
            "Closing cash after planned intercompany and external "
            "funding adjustments, converted into EUR."
        )
    )

    col3.metric(
        "Planned Funding (EUR)",
        f"€ {total_funding_eur:,.0f}"
    )

    col4.metric(
        "Liquidity Breach Days",
        f"{int(total_breaches)}"
    )

    # ----------------------------------------------
    # LIQUIDITY REQUIREMENT BY CURRENCY
    # ----------------------------------------------

    st.subheader(
        "Liquidity Requirement by Currency"
    )

    if not filtered_funding_plan.empty:

        liquidity_by_currency = (
            filtered_funding_plan
            .groupby(
                "currency",
                as_index=False
            )
            .agg(
                liquidity_requirement=(
                    "funding_amount",
                    "sum"
                ),
                requirement_eur=(
                    "funding_amount_eur",
                    "sum"
                )
            )
        )

        # Effective FX rate for each currency
        liquidity_by_currency["fx_rate_to_eur"] = (
            liquidity_by_currency["requirement_eur"]
            / liquidity_by_currency["liquidity_requirement"]
        )

        liquidity_display = liquidity_by_currency.copy()

        liquidity_display["Liquidity Requirement"] = (
            liquidity_display.apply(
                lambda row: format_currency(
                    row["liquidity_requirement"],
                    row["currency"]
                ),
                axis=1
            )
        )

        liquidity_display["FX Rate to EUR"] = (
            liquidity_display["fx_rate_to_eur"]
            .map(
                lambda value: f"{value:.4f}"
            )
        )

        liquidity_display["Requirement (EUR)"] = (
            liquidity_display["requirement_eur"]
            .map(
                lambda value: f"€ {value:,.0f}"
            )
        )

        liquidity_display = liquidity_display[
            [
                "currency",
                "Liquidity Requirement",
                "FX Rate to EUR",
                "Requirement (EUR)"
            ]
        ]

        liquidity_display = liquidity_display.rename(
            columns={
                "currency": "Currency"
            }
        )

        st.dataframe(
            liquidity_display,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "FX rates are based on the latest available "
            "forecast rates for each entity and currency."
        )

        st.markdown(
            f"**Total Liquidity Requirement (EUR): "
            f"€ {total_funding_eur:,.0f}**"
        )

    else:

        st.info(
            "No liquidity requirements for the selected filters."
        )


# --------------------------------------------------
# ADJUSTED CLOSING BALANCE FORECAST
# --------------------------------------------------

st.header("Adjusted Closing Balance Forecast")

if not filtered_forecast.empty:
    if "adjusted_balance" not in filtered_forecast.columns:
        st.error(
            "The forecast output does not contain 'adjusted_balance'. "
            "Please run forecast.py and verify the generated output."
        )
    else:
        # adjusted_balance includes the impact of planned intercompany
        # and external funding. Keep each currency separate: no FX conversion
        # and no aggregation across different currencies.
        chart_balance = filtered_forecast.copy()
        chart_balance["Entity Name"] = (
            chart_balance["entity_id"]
            .map(entity_name_map)
            .fillna(chart_balance["entity_id"])
        )

        currencies_in_view = [
            currency for currency in selected_currencies
            if currency in chart_balance["currency"].unique()
        ]

        if currencies_in_view:
            currency_tabs = st.tabs(currencies_in_view)

            for currency_tab, currency in zip(
                currency_tabs, currencies_in_view
            ):
                with currency_tab:
                    currency_data = chart_balance[
                        chart_balance["currency"] == currency
                    ]

                    balance_by_entity = (
                        currency_data
                        .groupby(
                            ["date", "Entity Name"],
                            as_index=False
                        )["adjusted_balance"]
                        .sum()
                    )

                    balance_chart = (
                        balance_by_entity
                        .pivot(
                            index="date",
                            columns="Entity Name",
                            values="adjusted_balance"
                        )
                        .sort_index()
                    )

                    st.line_chart(
                        balance_chart,
                        use_container_width=True,
                        y_label=f"Closing Balance ({currency})"
                    )
        else:
            st.info(
                "No adjusted closing balance data for the selected filters."
            )
else:
    st.info("No forecast data for the selected filters.")


# --------------------------------------------------
# CASH FLOW DETAILS (TABLE ONLY - NO CASH FLOW CHART)
# --------------------------------------------------

st.header("Cash Flow Details")

# Keep the transaction-level table, including intercompany and external
# funding movements. Amounts remain in each fund's original currency.
cash_flow_rows = []

cash_flows_path = DATA_DIR / "cash_flows.csv"

if cash_flows_path.exists():
    source_cash_flows = pd.read_csv(cash_flows_path)

    if not source_cash_flows.empty:
        source_cash_flows["value_date"] = pd.to_datetime(
            source_cash_flows["value_date"], errors="coerce"
        )

        source_cash_flows = source_cash_flows[
            source_cash_flows["entity_id"].isin(selected_entities)
            & source_cash_flows["currency"].isin(selected_currencies)
        ].copy()

        if not filtered_forecast.empty:
            source_cash_flows = source_cash_flows[
                source_cash_flows["value_date"].between(
                    filtered_forecast["date"].min(),
                    filtered_forecast["date"].max()
                )
            ]

        for _, row in source_cash_flows.iterrows():
            cash_flow_rows.append({
                "Value Date": row["value_date"],
                "Entity Name": entity_name_map.get(
                    row["entity_id"], row["entity_id"]
                ),
                "Amount": float(row["amount"]),
                "Currency": row["currency"],
                "Category": row.get("category", "Cash Flow"),
            })

if not funding_plan.empty:
    funding_rows = funding_plan.copy()
    funding_rows["value_date"] = pd.to_datetime(
        funding_rows["value_date"], errors="coerce"
    )
    funding_rows = funding_rows[
        funding_rows["currency"].isin(selected_currencies)
    ].copy()

    if not filtered_forecast.empty:
        funding_rows = funding_rows[
            funding_rows["value_date"].between(
                filtered_forecast["date"].min(),
                filtered_forecast["date"].max()
            )
        ]

    for _, row in funding_rows.iterrows():
        funding_amount = float(row["funding_amount"])
        funding_type = str(row["funding_type"]).upper()
        lender_id = row["lender_entity"]
        borrower_id = row["borrower_entity"]

        if funding_type == "INTERCOMPANY":
            if lender_id in selected_entities:
                cash_flow_rows.append({
                    "Value Date": row["value_date"],
                    "Entity Name": entity_name_map.get(lender_id, lender_id),
                    "Amount": -funding_amount,
                    "Currency": row["currency"],
                    "Category": "Intercompany Funding - Outflow",
                })

            if borrower_id in selected_entities:
                cash_flow_rows.append({
                    "Value Date": row["value_date"],
                    "Entity Name": entity_name_map.get(
                        borrower_id, borrower_id
                    ),
                    "Amount": funding_amount,
                    "Currency": row["currency"],
                    "Category": "Intercompany Funding - Inflow",
                })

        elif funding_type == "EXTERNAL" and borrower_id in selected_entities:
            cash_flow_rows.append({
                "Value Date": row["value_date"],
                "Entity Name": entity_name_map.get(
                    borrower_id, borrower_id
                ),
                "Amount": funding_amount,
                "Currency": row["currency"],
                "Category": "External Funding - Inflow",
            })

if cash_flow_rows:
    cash_flow_display = pd.DataFrame(
        cash_flow_rows,
        columns=[
            "Value Date",
            "Entity Name",
            "Amount",
            "Currency",
            "Category",
        ],
    ).sort_values(["Value Date", "Currency", "Entity Name"])

    table_display = cash_flow_display.copy()
    table_display["Value Date"] = table_display["Value Date"].dt.strftime(
        "%d/%m/%Y"
    )
    table_display["Amount"] = table_display.apply(
        lambda row: f"{row['Amount']:,.2f}",
        axis=1,
    )

    st.dataframe(
        table_display[
            ["Value Date", "Entity Name", "Amount", "Currency", "Category"]
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No cash-flow or funding movements for the selected filters.")


# --------------------------------------------------
# LIQUIDITY BUFFER MONITORING
# --------------------------------------------------

st.header("Liquidity Buffer Monitoring")

buffer_columns = [
    "date",
    "entity_id",
    "currency",
    "adjusted_balance",
    "minimum_buffer",
    "target_buffer",
    "minimum_buffer_gap",
    "minimum_buffer_status"
]

if not filtered_forecast.empty:

    buffer_display = filtered_forecast[
        buffer_columns
    ].copy()
    buffer_display["entity_name"] = buffer_display["entity_id"].map(
        entity_name_map
    ).fillna(buffer_display["entity_id"])
    buffer_display = buffer_display.drop(columns=["entity_id"])
    buffer_display = buffer_display.rename(
        columns={"entity_name": "Entity Name"}
    )

    # Display dates without time
    buffer_display["date"] = (
        buffer_display["date"]
        .dt.strftime("%d/%m/%Y")
    )

    amount_columns = [
        "adjusted_balance",
        "minimum_buffer",
        "target_buffer",
        "minimum_buffer_gap"
    ]

    for column in amount_columns:

        buffer_display[column] = (
            buffer_display.apply(
                lambda row: format_currency(
                    row[column],
                    row["currency"]
                ),
                axis=1
            )
        )

    st.dataframe(
        buffer_display,
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# FUNDING PLAN
# --------------------------------------------------

st.header("Funding Plan")

if funding_plan.empty:

    st.success(
        "No funding actions required."
    )

else:

    if filtered_funding_plan.empty:

        st.info(
            "No funding actions for the selected filters."
        )

    else:

        funding_display = (
            filtered_funding_plan.copy()
        )
        for entity_column in ["lender_entity", "borrower_entity"]:
            funding_display[entity_column] = (
                funding_display[entity_column]
                .map(entity_name_map)
                .fillna(funding_display[entity_column])
            )
        funding_display = funding_display.rename(
            columns={
                "lender_entity": "Lender Entity",
                "borrower_entity": "Borrower Entity",
            }
        )

        # Display dates without time
        for date_column in [
            "action_date",
            "value_date",
            "liquidity_need_date"
        ]:

            funding_display[date_column] = (
                funding_display[date_column]
                .dt.strftime("%d/%m/%Y")
            )

        # Format funding amounts in original currency
        funding_display["funding_amount_display"] = (
            funding_display.apply(
                lambda row: format_currency(
                    row["funding_amount"],
                    row["currency"]
                ),
                axis=1
            )
        )

        funding_columns = [
            "action_date",
            "value_date",
            "liquidity_need_date",
            "currency",
            "Lender Entity",
            "Borrower Entity",
            "funding_type",
            "funding_amount_display",
            "status"
        ]

        st.dataframe(
            funding_display[funding_columns],
            use_container_width=True,
            hide_index=True
        )


# --------------------------------------------------
# DATA EXPORT
# --------------------------------------------------

st.header("Export")

csv_data = filtered_forecast.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    label="Download Forecast CSV",
    data=csv_data,
    file_name="treasury_forecast.csv",
    mime="text/csv"
)


# --------------------------------------------------
# AI TREASURY ASSISTANT - GEMINI
# --------------------------------------------------

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

st.divider()

st.header("AI Treasury Assistant")

st.caption(
    "Ask Gemini questions about the liquidity forecast "
    "and funding requirements currently selected in the dashboard."
)

# Prepare forecast context for the AI
if not filtered_forecast.empty:

    # Latest forecast date
    latest_forecast_date = filtered_forecast["date"].max()

    latest_forecast = filtered_forecast[
        filtered_forecast["date"] == latest_forecast_date
    ].copy()

    # Summarize liquidity by entity and currency
    forecast_summary = (
        latest_forecast
        .groupby(
            ["entity_id", "currency"],
            as_index=False
        )
        .agg(
            closing_balance_eur=("closing_balance_eur", "sum"),
            adjusted_balance=("adjusted_balance", "sum"),
            minimum_buffer_gap=("minimum_buffer_gap", "sum"),
            liquidity_breach=("adjusted_liquidity_breach", "max")
        )
    )

    forecast_summary["closing_balance_eur"] = (
        forecast_summary["closing_balance_eur"].round(2)
    )
    fx_by_entity_currency = (
        latest_forecast
        .groupby(["entity_id", "currency"])["fx_rate_to_eur"]
        .first()
    )
    forecast_summary["fx_rate_to_eur"] = forecast_summary.apply(
        lambda row: fx_by_entity_currency.get(
            (row["entity_id"], row["currency"]), 1.0
        ),
        axis=1
    )
    forecast_summary["adjusted_balance_eur"] = (
        forecast_summary["adjusted_balance"]
        * forecast_summary["fx_rate_to_eur"]
    ).round(2)
    forecast_summary = forecast_summary.drop(
        columns=["fx_rate_to_eur"]
    )
    forecast_summary["entity_id"] = (
        forecast_summary["entity_id"].map(entity_name_map)
        .fillna(forecast_summary["entity_id"])
    )
    forecast_summary = forecast_summary.rename(
        columns={"entity_id": "entity_name"}
    )

    forecast_context = forecast_summary.to_dict(orient="records")

else:

    forecast_context = []

# Prepare funding context
if not filtered_funding_plan.empty:

    funding_context = filtered_funding_plan[
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

    # Convert technical entity IDs to readable names for the AI.
    for entity_column in ["lender_entity", "borrower_entity"]:
        funding_context[entity_column] = (
            funding_context[entity_column]
            .map(entity_name_map)
            .fillna(funding_context[entity_column])
        )

    funding_context = funding_context.rename(
        columns={
            "lender_entity": "lender_entity_name",
            "borrower_entity": "borrower_entity_name",
        }
    )

    # Convert dates to text for the API
    for column in [
        "action_date",
        "value_date",
        "liquidity_need_date"
    ]:

        funding_context[column] = (
            funding_context[column]
            .dt.strftime("%Y-%m-%d")
        )

    funding_context = funding_context.to_dict(orient="records")

else:

    funding_context = []

# User question
user_question = st.text_input(
    "Ask a Treasury question",
    placeholder=(
        "Example: Which entities require external funding?"
    ),
    key="treasury_ai_question"
)

if st.button("Ask Gemini", type="primary"):

    if not user_question.strip():

        st.warning("Please enter a question first.")

    else:

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:

            st.error(
                "Gemini API key not found. "
                "Please check your .env file."
            )

        else:

            try:

                client = genai.Client(api_key=api_key)

                treasury_context = {
                    "forecast_date": str(
                        latest_forecast_date.date()
                    ) if not filtered_forecast.empty else None,
                    "forecast_summary": forecast_context,
                    "funding_plan": funding_context
                }

                prompt = f"""
You are an AI Treasury Assistant.

Your role is to explain liquidity forecasts and funding
requirements using the data provided below. The data distinguishes
closing_balance_eur (before planned funding adjustments) from
adjusted_balance_eur (after planned intercompany and external funding).

IMPORTANT RULES:
1. Use only the supplied data for factual numerical claims.
2. Do not invent balances, funding amounts, FX rates,
   dates, entities, or liquidity risks.
3. If the data does not contain enough information,
   clearly say so.
4. Python is responsible for financial calculations.
   You are responsible for interpreting and explaining
   the results.
5. Distinguish clearly between facts and suggestions.
6. Answer in the same language as the user's question.
7. Be concise, professional, and suitable for a Treasury
   Analyst.

TREASURY DATA:
{treasury_context}

USER QUESTION:
{user_question}
"""

                with st.spinner(
                    "Gemini is analyzing the Treasury data..."
                ):

                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=prompt
                    )

                st.subheader("Gemini's Answer")

                if response.text:
                    st.markdown(response.text)
                else:
                    st.warning(
                        "Gemini returned an empty response. "
                        "Please try rephrasing the question."
                    )

            except Exception as error:

                st.error(
                    "Gemini could not answer the question. "
                    "Please check the API connection and try again."
                )

                st.caption(str(error))
