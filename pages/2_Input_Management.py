from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="Input Management | Treasury",
    page_icon="📝",
    layout="wide",
)

st.title("Input Management")
st.caption(
    "Edit Treasury forecast assumptions and input data. "
    "Changes are saved to the CSV input files used by forecast.py."
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
FORECAST_SCRIPT = PROJECT_DIR / "src" / "forecast.py"

INPUT_FILES = {
    "Opening Balances": "opening_balances.csv",
    "Cash Flows": "cash_flows.csv",
    "FX Rates": "fx_rates.csv",
    "Liquidity Buffers": "liquidity_buffers.csv",
}

DATE_COLUMNS = {
    "Opening Balances": ["as_of_date"],
    "Cash Flows": ["value_date"],
    "FX Rates": ["rate_date"],
    "Liquidity Buffers": ["effective_date"],
}


@st.cache_data
def load_input_data(filename: str) -> pd.DataFrame:
    """input CSV from the project's data folder."""
    return pd.read_csv(DATA_DIR / filename)


@st.cache_data
def load_entity_mapping() -> dict:
    """Return Entity ID -> Entity Name mapping from entities.csv."""
    entities_file = DATA_DIR / "entities.csv"
    if not entities_file.exists():
        return {}
    entities_df = pd.read_csv(entities_file)
    if not {"entity_id", "entity_name"}.issubset(entities_df.columns):
        return {}
    return dict(zip(entities_df["entity_id"], entities_df["entity_name"]))


def show_entity_names(df: pd.DataFrame) -> pd.DataFrame:
    """Replace entity_id with entity_name in the editor view only."""
    result = df.copy()
    if "entity_id" in result.columns:
        mapping = load_entity_mapping()
        result["entity_id"] = result["entity_id"].map(mapping).fillna(
            result["entity_id"]
        )
        result = result.rename(columns={"entity_id": "entity_name"})
    return result


def restore_entity_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the visible entity_name field back to entity_id for CSV storage."""
    result = df.copy()
    if "entity_name" in result.columns:
        mapping = load_entity_mapping()
        name_to_id = {name: entity_id for entity_id, name in mapping.items()}
        result["entity_name"] = result["entity_name"].map(name_to_id).fillna(
            result["entity_name"]
        )
        result = result.rename(columns={"entity_name": "entity_id"})
    return result


def normalize_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Convert editable date columns to Streamlit-friendly date values."""
    result = df.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_datetime(
                result[column], errors="coerce"
            ).dt.date
    return result


def save_input_data(label: str, edited_df: pd.DataFrame) -> None:
    """Validate and save an edited input table to its CSV file."""
    filename = INPUT_FILES[label]
    result = edited_df.copy()

    # Remove rows explicitly selected for deletion in the Cash Flows editor.
    if label == "Cash Flows" and "delete_row" in result.columns:
        result = result.loc[~result["delete_row"].fillna(False)].drop(
            columns=["delete_row"]
        )

    result = restore_entity_ids(result)

    # Dates are stored in ISO format in the CSV files.
    for column in DATE_COLUMNS[label]:
        if column in result.columns:
            result[column] = pd.to_datetime(
                result[column], errors="raise"
            ).dt.strftime("%Y-%m-%d")

    # Ensure numeric columns remain numeric.
    numeric_columns = {
        "Opening Balances": ["opening_balance"],
        "Cash Flows": ["amount"],
        "FX Rates": ["rate"],
        "Liquidity Buffers": ["minimum_buffer", "target_buffer"],
    }[label]

    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column], errors="raise"
            )

    # Basic checks before writing.
    if label == "Opening Balances":
        required = ["as_of_date", "entity_id", "account_id",
                    "currency", "opening_balance"]
        if result[required].isna().any().any():
            raise ValueError("Opening balances contains empty required fields.")

    elif label == "Cash Flows":
        required = ["flow_id", "entity_id", "account_id", "value_date",
                    "amount", "currency"]
        if result[required].isna().any().any():
            raise ValueError("Cash flows contains empty required fields.")
        if result["flow_id"].duplicated().any():
            raise ValueError("Each cash flow must have a unique flow_id.")

    elif label == "FX Rates":
        required = ["rate_date", "base_currency", "quote_currency", "rate"]
        if result[required].isna().any().any():
            raise ValueError("FX rates contains empty required fields.")
        if (result["rate"] <= 0).any():
            raise ValueError("FX rates must be greater than zero.")

    elif label == "Liquidity Buffers":
        required = ["entity_id", "currency", "minimum_buffer",
                    "target_buffer", "effective_date"]
        if result[required].isna().any().any():
            raise ValueError("Liquidity buffers contains empty required fields.")
        if (result["minimum_buffer"] < 0).any() or (
            result["target_buffer"] < result["minimum_buffer"]
        ).any():
            raise ValueError(
                "Buffers must be non-negative and target_buffer "
                "must be greater than or equal to minimum_buffer."
            )

    output_path = DATA_DIR / filename
    result.to_csv(output_path, index=False)
    load_input_data.clear()


# --------------------------------------------------
# INPUT TABLE EDITORS
# --------------------------------------------------
st.info(
    "Edit the tables below, then click the Save button for that section. "
    "The forecast is not recalculated until you click Run Forecast."
)

tabs = st.tabs(list(INPUT_FILES.keys()))
edited_tables = {}

for tab, label in zip(tabs, INPUT_FILES.keys()):
    with tab:
        filename = INPUT_FILES[label]
        try:
            original_df = load_input_data(filename)
        except FileNotFoundError:
            st.error(f"Input file not found: {DATA_DIR / filename}")
            continue

        editor_df = normalize_dates(original_df, DATE_COLUMNS[label])
        if label in ["Opening Balances", "Cash Flows", "Liquidity Buffers"]:
            editor_df = show_entity_names(editor_df)

        # Use sensible editor types for the known input columns.
        column_config = {}
        if label in ["Opening Balances", "Cash Flows", "Liquidity Buffers"]:
            entity_names = list(load_entity_mapping().values())
            column_config["entity_name"] = st.column_config.SelectboxColumn(
                "Entity Name",
                options=entity_names,
                required=True,
            )

        if label == "Opening Balances":
            column_config.update({
                "as_of_date": st.column_config.DateColumn("As of date"),
                "opening_balance": st.column_config.NumberColumn(
                    "Opening balance", format="%,.2f"
                ),
            })
        elif label == "Cash Flows":
            # Explicit delete flag makes row removal clear and reliable.
            if "delete_row" not in editor_df.columns:
                editor_df["delete_row"] = False
            column_config.update({
                "delete_row": st.column_config.CheckboxColumn(
                    "Delete row",
                    help="Check this box to remove the cash flow when you save.",
                    default=False,
                ),
                "value_date": st.column_config.DateColumn("Value date"),
                "amount": st.column_config.NumberColumn(
                    "Amount", format="%,.2f"
                ),
                "status": st.column_config.SelectboxColumn(
                    "Status", options=["Committed", "Forecast", "Pending"]
                ),
                "scenario": st.column_config.SelectboxColumn(
                    "Scenario", options=["Base", "Upside", "Downside"]
                ),
            })
        elif label == "FX Rates":
            column_config = {
                "rate_date": st.column_config.DateColumn("Rate date"),
                "rate": st.column_config.NumberColumn(
                    "FX rate", format="%,.6f"
                ),
            }
        elif label == "Liquidity Buffers":
            column_config.update({
                "effective_date": st.column_config.DateColumn(
                    "Effective date"
                ),
                "minimum_buffer": st.column_config.NumberColumn(
                    "Minimum buffer", format="%,.2f"
                ),
                "target_buffer": st.column_config.NumberColumn(
                    "Target buffer", format="%,.2f"
                ),
            })

        if label == "Cash Flows":
            st.caption(
                "To delete a cash flow, tick 'Delete row' and click "
                "'Save Cash Flows'. The selected rows will be removed "
                "from the CSV."
            )

        edited_df = st.data_editor(
            editor_df,
            key=f"editor_{label}",
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
        )
        edited_tables[label] = edited_df

        col_save, col_reset = st.columns([1, 1])
        with col_save:
            if st.button(
                f"Save {label}",
                key=f"save_{label}",
                type="primary",
            ):
                try:
                    save_input_data(label, edited_df)
                    st.success(f"{label} saved.")
                except Exception as error:
                    st.error(f"Could not save {label}: {error}")

        with col_reset:
            if st.button(
                f"Reload saved CSV",
                key=f"reload_{label}",
            ):
                load_input_data.clear()
                st.session_state.pop(f"editor_{label}", None)
                st.rerun()


# --------------------------------------------------
# RUN FORECAST
# --------------------------------------------------
st.divider()
st.header("Recalculate Forecast")

st.warning(
    "Running the forecast overwrites the files in the outputs folder "
    "with results calculated from the currently saved input CSVs."
)

if st.button("Run Forecast", type="primary", use_container_width=True):
    if not FORECAST_SCRIPT.exists():
        st.error(f"Forecast script not found: {FORECAST_SCRIPT}")
    else:
        with st.spinner("Running the Treasury forecast engine..."):
            try:
                completed = subprocess.run(
                    [sys.executable, str(FORECAST_SCRIPT)],
                    cwd=PROJECT_DIR,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                st.cache_data.clear()
                st.success(
                    "Forecast completed. Open the Overview page to see "
                    "the updated liquidity forecast and funding plan."
                )
                if completed.stdout.strip():
                    with st.expander("Forecast log"):
                        st.code(completed.stdout)
            except subprocess.CalledProcessError as error:
                st.error("Forecast execution failed.")
                if error.stdout:
                    st.text("Standard output:")
                    st.code(error.stdout)
                if error.stderr:
                    st.text("Error details:")
                    st.code(error.stderr)
