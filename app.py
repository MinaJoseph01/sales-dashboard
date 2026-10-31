"""
app.py
------
The dashboard page. Run it with:   streamlit run app.py

Streamlit re-runs this whole file, top to bottom, every time the user touches a
widget. The flow each time is:
    1. Choose the data (default CSV or an uploaded one)  -> load + clean it
    2. Read the sidebar filters
    3. Filter the data  -> calculate KPIs  -> draw charts
Nothing is hardcoded: every number comes from the filtered data.
"""

from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.charts import (
    bottom_products,
    monthly_revenue_trend,
    profitability_by_category,
    revenue_by_category,
    revenue_by_channel,
    revenue_by_region,
    top_products,
)
from src.data_loader import REQUIRED_COLUMNS, DataValidationError, load_sales_data
from src.metrics import (
    compare_kpis,
    filter_by_date,
    filter_by_dimensions,
    format_change,
    format_value,
    get_previous_period,
    has_full_previous_period,
)

DATA_PATH = Path(__file__).parent / "data" / "sales_data.csv"

# set_page_config must be the first Streamlit command in the script
st.set_page_config(page_title="Sales Performance Dashboard", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 2.5rem; padding-bottom: 2rem;}
    [data-testid="stMetricLabel"] p {font-size: 0.85rem; color: #6B7280;}
    [data-testid="stMetricValue"] {font-size: 1.6rem; font-weight: 600;}
    h1 {font-weight: 700; letter-spacing: -0.5px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------
# Data loading (cached, so a click on a filter doesn't re-read the file)
# ---------------------------------------------------------------
@st.cache_data(show_spinner="Loading data...")
def load_default_file(path: str, modified_time: float):
    """`modified_time` is part of the cache key: replace the CSV and the cache refreshes itself."""
    return load_sales_data(path)


@st.cache_data(show_spinner="Checking your file...")
def load_uploaded_file(file_bytes: bytes, file_name: str, dayfirst: bool):
    """A new upload (or a changed date setting) gets a new cache entry, so the dashboard refreshes."""
    return load_sales_data(io.BytesIO(file_bytes), dayfirst=dayfirst)


def build_template_csv() -> bytes:
    """A tiny, valid example file for the 'Download CSV template' button."""
    rows = [
        ["ORD-0001", "2025-01-15", "Europe", "Germany", "Laptop Pro 15", "Technology", "Online", 2, 1250.00, 2500.00, 1900.00, 600.00],
        ["ORD-0001", "2025-01-15", "Europe", "Germany", "Wireless Mouse", "Accessories", "Online", 3, 35.00, 105.00, 60.00, 45.00],
        ["ORD-0002", "2025-01-16", "North America", "United States", "Ergonomic Chair", "Furniture", "Retail Store", 1, 340.00, 340.00, 270.00, 70.00],
        ["ORD-0003", "2025-01-18", "Asia Pacific", "India", "Notebook Set", "Office Supplies", "Distributor", 10, 14.00, 140.00, 70.00, 70.00],
        ["ORD-0004", "2025-01-20", "Middle East", "United Arab Emirates", "USB-C Hub", "Accessories", "Mobile App", 4, 49.00, 196.00, 105.00, 91.00],
    ]
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS).to_csv(index=False).encode("utf-8")


def choose_data():
    """Sidebar 'Data' section. Returns (DataFrame, LoadReport, source name, was_uploaded)."""
    st.sidebar.header("Data")
    uploaded = st.sidebar.file_uploader(
        "Upload a sales CSV", type=["csv"],
        help="Needs the same columns as the template. Remove the file (x) to go back to the sample data.",
    )
    st.sidebar.download_button(
        "Download CSV template", data=build_template_csv(),
        file_name="sales_template.csv", mime="text/csv", width="stretch",
    )

    if uploaded is not None:
        date_format = st.sidebar.radio(
            "Date format in your file", ["YYYY-MM-DD or MM/DD/YYYY", "DD/MM/YYYY"],
            help="Only matters for dates like 03/04/2025. Dates written as 2025-04-03 are always read correctly.",
        )
        try:
            df, report = load_uploaded_file(uploaded.getvalue(), uploaded.name, date_format == "DD/MM/YYYY")
            return df, report, uploaded.name, True
        except DataValidationError as err:
            st.sidebar.error(f"Upload rejected: {err}")
        except Exception as err:  # anything unexpected: don't show a raw traceback to the user
            st.sidebar.error("Something unexpected went wrong while reading this file.")
            with st.sidebar.expander("Technical details"):
                st.code(repr(err))
        st.sidebar.warning("Showing the sample data instead.")

    if not DATA_PATH.exists():
        st.error("Sample data not found. In PowerShell, run:  python generate_data.py")
        st.stop()
    try:
        df, report = load_default_file(str(DATA_PATH), DATA_PATH.stat().st_mtime)
    except DataValidationError as err:
        st.error(f"The default data file (data/sales_data.csv) is not valid: {err}")
        st.stop()
    return df, report, DATA_PATH.name, False


def choose_filters(df: pd.DataFrame):
    """Sidebar 'Filters' section. Returns the user's selections."""
    st.sidebar.header("Filters")
    min_date, max_date = df["Order_Date"].min().date(), df["Order_Date"].max().date()
    # Start on the most recent 12 months, so the "previous period" comparison has data to show
    default_start = max(min_date, max_date - timedelta(days=364))
    selected = st.sidebar.date_input(
        "Date range", value=(default_start, max_date), min_value=min_date, max_value=max_date,
    )

    # No `key=` on these widgets on purpose: when new data brings new options,
    # Streamlit treats them as new widgets and resets them to "everything selected".
    regions_all = sorted(df["Region"].unique())
    categories_all = sorted(df["Category"].unique())
    channels_all = sorted(df["Sales_Channel"].unique())
    regions = st.sidebar.multiselect("Region", regions_all, default=regions_all)
    categories = st.sidebar.multiselect("Product Category", categories_all, default=categories_all)
    channels = st.sidebar.multiselect("Sales Channel", channels_all, default=channels_all)
    return selected, regions, categories, channels


def show(fig) -> None:
    """Draw a Plotly chart inside a bordered panel."""
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


# ---------------------------------------------------------------
# The page
# ---------------------------------------------------------------
df, report, source, was_uploaded = choose_data()

if was_uploaded:
    st.sidebar.success(f"Loaded {report.rows_kept:,} of {report.rows_read:,} rows from {source}")
if report.notes:
    with st.sidebar.expander(f"Data quality notes ({len(report.notes)})"):
        for note in report.notes:
            st.write("• " + note)

selected_dates, regions, categories, channels = choose_filters(df)

st.title("Sales Performance Dashboard")
st.caption(
    f"Data: {source} · {len(df):,} rows · "
    f"{df['Order_Date'].min():%d %b %Y} to {df['Order_Date'].max():%d %b %Y}"
)

# Guard clauses: stop early with a helpful message instead of showing broken charts
if not (isinstance(selected_dates, tuple) and len(selected_dates) == 2):
    st.info("Pick both a start date and an end date in the sidebar.")
    st.stop()
if not (regions and categories and channels):
    st.warning("Select at least one option in every filter to see results.")
    st.stop()

start, end = selected_dates

# Apply filters. Region/Category/Channel apply to BOTH periods; only the dates differ.
base = filter_by_dimensions(df, regions, categories, channels)
current = filter_by_date(base, start, end)
prev_start, prev_end = get_previous_period(start, end)
previous = filter_by_date(base, prev_start, prev_end)

if current.empty:
    st.warning("No orders match the selected filters and date range. Try widening them.")
    st.stop()

# ---- Executive overview ----------------------------------------
st.subheader("Executive Overview")
cards = compare_kpis(current, previous)
for column, card in zip(st.columns(len(cards)), cards):
    delta = None if card.change is None else format_change(card.change, card.kind)
    column.metric(card.label, format_value(card.value, card.kind), delta=delta, border=True)

n_days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
if previous.empty:
    st.caption("No data in the previous period, so no comparison is shown.")
else:
    st.caption(
        f"Changes compare {start:%d %b %Y} to {end:%d %b %Y} with the previous {n_days} days "
        f"({prev_start:%d %b %Y} to {prev_end:%d %b %Y})."
    )
    if not has_full_previous_period(df, prev_start):
        st.caption("Note: the data covers only part of the previous period, so changes may be misleading.")

# ---- Sales analysis --------------------------------------------
st.subheader("Sales Analysis")
show(monthly_revenue_trend(current))

left, right = st.columns(2)
with left:
    show(revenue_by_region(current))
with right:
    show(revenue_by_channel(current))

left, right = st.columns(2)
with left:
    show(revenue_by_category(current))
with right:
    show(profitability_by_category(current))

left, right = st.columns(2)
with left:
    show(top_products(current))
with right:
    show(bottom_products(current))

# ---- Data and definitions --------------------------------------
with st.expander("View and download the filtered data"):
    st.dataframe(
        current, width="stretch", hide_index=True,
        column_config={"Order_Date": st.column_config.DateColumn("Order_Date", format="YYYY-MM-DD")},
    )
    st.download_button(
        "Download filtered data (CSV)", data=current.to_csv(index=False).encode("utf-8"),
        file_name="filtered_sales_data.csv", mime="text/csv",
    )

with st.expander("How the numbers are calculated"):
    st.markdown(
        """
        | Metric | Calculation |
        |---|---|
        | Revenue | Quantity × Unit_Price |
        | Profit | Revenue − Cost (Cost is the total cost of the order line) |
        | Total Orders | Number of unique Order_IDs |
        | Average Order Value | Total Revenue ÷ Total Orders |
        | Profit Margin | Total Profit ÷ Total Revenue × 100 |
        | Previous period | Same number of days, ending the day before the selected start date |
        | Margin change | Shown in percentage points (pp), not percent |
        """
    )