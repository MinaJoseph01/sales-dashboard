"""
Automated checks for the Sales Dashboard.  Run them with:   pytest

Sections:
  A. Synthetic data     B. Data loader     C. Metrics     D. Charts     E. The Streamlit app
"""

import io
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest
from streamlit.testing.v1 import AppTest

from generate_data import generate_sales_data
from src import charts
from src.data_loader import DataValidationError, load_sales_data
from src.metrics import (
    calculate_kpis, compare_kpis, filter_by_date, filter_by_dimensions,
    format_change, format_value, get_previous_period, percent_change,
)

ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
DATA_FILE = ROOT / "data" / "sales_data.csv"

HEADER = "Order_ID,Order_Date,Region,Country,Product,Category,Sales_Channel,Quantity,Unit_Price,Revenue,Cost,Profit"
GOOD_ROW = "ORD-1,2025-01-15,Europe,Germany,Laptop,Technology,Online,2,100,200,120,80"


def csv_text(*rows):
    return io.StringIO("\n".join([HEADER, *rows]) + "\n")


@pytest.fixture(scope="module")
def sales_df(tmp_path_factory):
    """A freshly generated dataset, loaded through the real loader."""
    path = tmp_path_factory.mktemp("data") / "sales.csv"
    generate_sales_data().to_csv(path, index=False)
    df, _ = load_sales_data(path)
    return df


@pytest.fixture
def tiny_df():
    """3 lines, 2 orders - small enough to check by hand (see test_kpis_match_hand_calculation)."""
    return pd.DataFrame({
        "Order_ID": ["A", "A", "B"],
        "Order_Date": pd.to_datetime(["2025-01-10", "2025-01-10", "2025-01-20"]),
        "Region": ["Europe", "Europe", "Asia Pacific"],
        "Category": ["Technology", "Furniture", "Technology"],
        "Sales_Channel": ["Online", "Online", "Retail Store"],
        "Quantity": [1, 2, 3],
        "Revenue": [100.0, 50.0, 150.0],
        "Profit": [30.0, 10.0, -10.0],
    })


# =====================================================================
# A. Synthetic data
# =====================================================================
def test_generated_data_meets_requirements():
    raw = generate_sales_data()
    assert len(raw) >= 1000
    assert list(raw.columns) == ["Order_ID", "Order_Date", "Region", "Country", "Product", "Category",
                                 "Sales_Channel", "Quantity", "Unit_Price", "Revenue", "Cost", "Profit"]
    assert (raw["Revenue"] - raw["Quantity"] * raw["Unit_Price"]).abs().max() < 0.01
    assert (raw["Profit"] - (raw["Revenue"] - raw["Cost"])).abs().max() < 0.01
    assert not raw.isna().any().any()
    assert not raw.duplicated().any()
    assert raw["Order_ID"].nunique() < len(raw)          # some orders have several lines


# =====================================================================
# B. Data loader
# =====================================================================
def test_messy_file_is_cleaned():
    messy = csv_text(
        "ORD-1,2025-01-05,Europe,France,Laptop,Technology,Online,2,\"$1,000.00\",,1500,",   # revenue/profit missing
        "ORD-1,2025-01-05,Europe,France,Laptop,Technology,Online,2,\"$1,000.00\",,1500,",   # exact duplicate
        "ORD-2,not a date,Europe,France,Mouse,Accessories,Online,1,30,30,15,15",            # bad date
        "ORD-3,2025-01-07,Europe,France,Mouse,Accessories,Online,abc,30,30,15,15",          # bad quantity
        "ORD-4,2025-01-08,Asia Pacific,India,Chair,Furniture,Retail Store,3,100,300,200,100",
        "ORD-5,2025-01-09,Asia Pacific,India,Chair,Furniture,Retail Store,-1,100,-100,50,-150",  # negative qty
    )
    df, report = load_sales_data(messy)
    assert (report.rows_read, report.rows_kept) == (6, 2)
    assert set(df["Order_ID"]) == {"ORD-1", "ORD-4"}
    row = df[df["Order_ID"] == "ORD-1"].iloc[0]
    assert row["Unit_Price"] == 1000.0 and row["Revenue"] == 2000.0 and row["Profit"] == 500.0


def test_missing_text_becomes_unknown():
    df, report = load_sales_data(csv_text("ORD-1,2025-01-15,,Germany,Laptop,Technology,Online,2,100,200,120,80"))
    assert df.loc[0, "Region"] == "Unknown"
    assert any("Unknown" in note for note in report.notes)


def test_dates_and_numbers_are_converted():
    df, _ = load_sales_data(csv_text(
        "ORD-1,2025-01-15,Europe,Germany,Laptop,Technology,Online,2,\"$1,250.50\",2501,1900,601",
        "ORD-2,Jan 16 2025,Europe,Germany,Laptop,Technology,Online,1,100,100,60,40",
    ))
    assert pd.api.types.is_datetime64_any_dtype(df["Order_Date"])
    assert list(df["Order_Date"].dt.day) == [15, 16]
    assert df.loc[0, "Unit_Price"] == 1250.5

def test_ambiguous_dates_follow_the_chosen_format():
    row = "ORD-1,03/04/2025,Europe,Germany,Laptop,Technology,Online,2,100,200,120,80"
    month_first, _ = load_sales_data(csv_text(row))
    day_first, _ = load_sales_data(csv_text(row), dayfirst=True)
    assert month_first.loc[0, "Order_Date"] == pd.Timestamp("2025-03-04")
    assert day_first.loc[0, "Order_Date"] == pd.Timestamp("2025-04-03")


def test_iso_dates_are_never_swapped_even_with_dayfirst():
    iso_row = "ORD-1,2025-01-05,Europe,Germany,Laptop,Technology,Online,2,100,200,120,80"
    for dayfirst in (False, True):
        df, _ = load_sales_data(csv_text(iso_row), dayfirst=dayfirst)
        assert df.loc[0, "Order_Date"] == pd.Timestamp("2025-01-05")


def test_column_names_are_case_and_space_insensitive():
    text = io.StringIO(HEADER.lower().replace("_", " ") + "\n" + GOOD_ROW + "\n")
    df, _ = load_sales_data(text)
    assert "Order_Date" in df.columns and len(df) == 1


def test_mismatched_revenue_is_kept_but_warned():
    df, report = load_sales_data(csv_text("ORD-1,2025-01-15,Europe,Germany,Laptop,Technology,Online,2,100,999,120,879"))
    assert df.loc[0, "Revenue"] == 999
    assert any("Warning" in note for note in report.notes)


@pytest.mark.parametrize("content", [
    "",                                   # empty file
    "Name,Age\nAnna,30\n",                # wrong columns
    HEADER + "\n",                        # headings but no rows
    HEADER + "\nORD-1,not a date,Europe,Germany,Laptop,Technology,Online,2,100,200,120,80\n",  # nothing valid left
])
def test_invalid_files_raise_clear_error(content):
    with pytest.raises(DataValidationError):
        load_sales_data(io.StringIO(content))


# =====================================================================
# C. Metrics
# =====================================================================
def test_kpis_match_hand_calculation(tiny_df):
    k = calculate_kpis(tiny_df)
    assert k["total_revenue"] == 300            # 100 + 50 + 150
    assert k["total_orders"] == 2               # A and B (A has two lines)
    assert k["units_sold"] == 6                 # 1 + 2 + 3
    assert k["aov"] == 150                      # 300 / 2 orders, NOT 300 / 3 lines
    assert k["total_profit"] == 30              # 30 + 10 - 10
    assert k["profit_margin"] == pytest.approx(10.0)


def test_kpis_are_not_hardcoded(tiny_df):
    doubled = tiny_df.assign(Revenue=tiny_df["Revenue"] * 2)
    assert calculate_kpis(doubled)["total_revenue"] == 600


def test_empty_data_gives_zeros_not_errors(tiny_df):
    k = calculate_kpis(tiny_df.iloc[0:0])
    assert k["total_revenue"] == 0 and k["aov"] == 0 and k["profit_margin"] == 0


@pytest.mark.parametrize("start, end, expected_start, expected_end", [
    ("2025-01-01", "2025-03-31", "2024-10-03", "2024-12-31"),   # 90 days
    ("2024-01-01", "2024-03-31", "2023-10-02", "2023-12-31"),   # 91 days (leap year)
    ("2025-03-10", "2025-03-10", "2025-03-09", "2025-03-09"),   # a single day
])
def test_previous_period(start, end, expected_start, expected_end):
    prev_start, prev_end = get_previous_period(start, end)
    assert (str(prev_start.date()), str(prev_end.date())) == (expected_start, expected_end)


def test_percent_change_and_formatting():
    assert percent_change(150, 100) == 50
    assert percent_change(100, 0) is None
    assert format_value(1_750_000, "currency") == "$1.75M"
    assert format_value(12_345, "currency") == "$12.3K"
    assert format_value(999.5, "currency") == "$999.50"
    assert format_value(25.386, "percent") == "25.4%"
    assert format_value(1200, "number") == "1,200"
    assert format_change(None, "currency") == "n/a"
    assert format_change(12.34, "currency") == "+12.3%"
    assert format_change(-3.5, "percent") == "-3.5 pp"


def test_compare_kpis_without_previous_data_shows_no_change(tiny_df):
    cards = compare_kpis(tiny_df, tiny_df.iloc[0:0])
    assert all(card.change is None for card in cards)


def test_date_filter_includes_both_end_dates(tiny_df):
    assert len(filter_by_date(tiny_df, "2025-01-10", "2025-01-10")) == 2
    assert len(filter_by_date(tiny_df, "2025-01-10", "2025-01-20")) == 3
    assert len(filter_by_date(tiny_df, "2025-01-11", "2025-01-19")) == 0


def test_dimension_filters(tiny_df):
    assert len(filter_by_dimensions(tiny_df)) == 3                                   # None = no filter
    assert len(filter_by_dimensions(tiny_df, regions=[])) == 0                       # empty list = nothing
    assert len(filter_by_dimensions(tiny_df, regions=["Europe"])) == 2
    assert len(filter_by_dimensions(tiny_df, regions=["Europe"], categories=["Technology"])) == 1
    assert len(filter_by_dimensions(tiny_df, channels=["Retail Store"])) == 1


def test_filters_partition_the_data(sales_df):
    """Splitting by every region (or category, or channel) and adding up must give the grand total."""
    total = sales_df["Revenue"].sum()
    for column, argument in [("Region", "regions"), ("Category", "categories"), ("Sales_Channel", "channels")]:
        parts = sum(filter_by_dimensions(sales_df, **{argument: [value]})["Revenue"].sum()
                    for value in sales_df[column].unique())
        assert parts == pytest.approx(total)


# =====================================================================
# D. Charts
# =====================================================================
ALL_CHARTS = [
    charts.monthly_revenue_trend, charts.revenue_by_region, charts.revenue_by_channel,
    charts.revenue_by_category, charts.top_products, charts.bottom_products,
    charts.profitability_by_category,
]


@pytest.mark.parametrize("chart_function", ALL_CHARTS)
def test_every_chart_builds_and_survives_empty_data(chart_function, sales_df):
    assert isinstance(chart_function(sales_df), go.Figure)
    empty_figure = chart_function(sales_df.iloc[0:0])
    assert "No data" in empty_figure.layout.annotations[0].text


def test_chart_numbers_match_pandas(sales_df):
    total = sales_df["Revenue"].sum()
    assert sum(charts.monthly_revenue_trend(sales_df).data[0].y) == pytest.approx(total)
    assert sum(charts.revenue_by_region(sales_df).data[0].x) == pytest.approx(total)
    assert sum(charts.revenue_by_channel(sales_df).data[0].x) == pytest.approx(total)
    assert sum(charts.revenue_by_category(sales_df).data[0].values) == pytest.approx(total)
    assert sum(charts.profitability_by_category(sales_df).data[0].y) == pytest.approx(sales_df["Profit"].sum())
    by_product = sales_df.groupby("Product")["Revenue"].sum()
    assert set(charts.top_products(sales_df).data[0].y) == set(by_product.nlargest(5).index)
    assert set(charts.bottom_products(sales_df).data[0].y) == set(by_product.nsmallest(5).index)


def test_charts_change_when_filters_change(sales_df):
    europe = filter_by_dimensions(sales_df, regions=["Europe"])
    assert sum(charts.revenue_by_region(europe).data[0].x) == pytest.approx(europe["Revenue"].sum())
    assert list(charts.revenue_by_region(europe).data[0].y) == ["Europe"]


# =====================================================================
# E. The Streamlit app (run headlessly, like a user clicking around)
# =====================================================================
needs_data = pytest.mark.skipif(not DATA_FILE.exists(), reason="Run `python generate_data.py` first")


def open_app():
    return AppTest.from_file(str(APP_FILE), default_timeout=60).run()


def upload(app, name, content):
    app.sidebar.file_uploader[0].upload(name, content, "text/csv").run()
    return app


@needs_data
def test_app_loads_and_default_kpis_are_correct():
    app = open_app()
    assert not app.exception
    assert [m.label for m in app.metric] == [
        "Total Revenue", "Total Orders", "Units Sold", "Avg Order Value", "Total Profit", "Profit Margin"]

    # Independent calculation of the default view (latest 365 days vs the 365 days before)
    df, _ = load_sales_data(DATA_FILE)
    end = df["Order_Date"].max()
    start = end - pd.Timedelta(days=364)
    now = df[(df["Order_Date"] >= start) & (df["Order_Date"] <= end)]
    before = df[(df["Order_Date"] >= start - pd.Timedelta(days=365)) & (df["Order_Date"] < start)]
    assert app.metric[0].value == format_value(now["Revenue"].sum(), "currency")
    assert app.metric[1].value == f"{now['Order_ID'].nunique():,}"
    expected_change = (now["Revenue"].sum() - before["Revenue"].sum()) / before["Revenue"].sum() * 100
    assert app.metric[0].delta == f"{expected_change:+.1f}%"


@needs_data
def test_region_filter_updates_kpis():
    app = open_app()
    df, _ = load_sales_data(DATA_FILE)
    end = df["Order_Date"].max()
    start = end - pd.Timedelta(days=364)
    europe = df[(df["Region"] == "Europe") & (df["Order_Date"] >= start) & (df["Order_Date"] <= end)]

    app.sidebar.multiselect[0].set_value(["Europe"]).run()
    assert not app.exception
    assert app.metric[0].value == format_value(europe["Revenue"].sum(), "currency")
    assert app.metric[1].value == f"{europe['Order_ID'].nunique():,}"


@needs_data
def test_category_and_channel_filters_update_kpis():
    app = open_app()
    df, _ = load_sales_data(DATA_FILE)
    end = df["Order_Date"].max()
    start = end - pd.Timedelta(days=364)
    subset = df[(df["Category"] == "Technology") & (df["Sales_Channel"] == "Online")
                & (df["Order_Date"] >= start) & (df["Order_Date"] <= end)]

    app.sidebar.multiselect[1].set_value(["Technology"]).run()
    app.sidebar.multiselect[2].set_value(["Online"]).run()
    assert app.metric[0].value == format_value(subset["Revenue"].sum(), "currency")


@needs_data
def test_date_range_updates_kpis():
    import datetime as dt
    app = open_app()
    df, _ = load_sales_data(DATA_FILE)
    q1 = df[(df["Order_Date"] >= "2024-01-01") & (df["Order_Date"] <= "2024-03-31")]

    app.sidebar.date_input[0].set_value((dt.date(2024, 1, 1), dt.date(2024, 3, 31))).run()
    assert not app.exception
    assert app.metric[0].value == format_value(q1["Revenue"].sum(), "currency")
    assert app.metric[0].delta == ""        # no data before Jan 2024, so no comparison is shown


@needs_data
def test_incomplete_filters_show_messages_not_errors():
    import datetime as dt
    app = open_app()
    app.sidebar.multiselect[0].set_value([]).run()
    assert not app.exception and any("at least one" in w.value for w in app.warning)

    app = open_app()
    app.sidebar.date_input[0].set_value((dt.date(2024, 1, 1),)).run()
    assert not app.exception and any("start date and an end date" in i.value for i in app.info)


@needs_data
def test_valid_upload_replaces_the_data():
    new_file = "\n".join([
        HEADER,
        "ORD-1,2025-01-15,Europe,Germany,Laptop Pro 15,Technology,Online,2,1250,2500,1900,600",
        "ORD-1,2025-01-15,Europe,Germany,Wireless Mouse,Accessories,Online,3,35,105,60,45",
        "ORD-2,2025-01-16,North America,United States,Chair,Furniture,Retail Store,1,340,340,270,70",
    ]).encode()
    app = upload(open_app(), "new_sales.csv", new_file)
    assert not app.exception
    assert app.metric[0].value == "$2,945.00"          # 2500 + 105 + 340
    assert app.metric[1].value == "2"                  # two unique orders
    assert any("Loaded 3 of 3 rows" in s.value for s in app.sidebar.success)



@needs_data
def test_date_format_choice_changes_how_an_upload_is_read():
    file = "\n".join([HEADER, "ORD-1,03/04/2025,Europe,Germany,Laptop,Technology,Online,2,100,200,120,80"]).encode()
    app = upload(open_app(), "excel_export.csv", file)
    assert any("04 Mar 2025" in c.value for c in app.caption)

    app.sidebar.radio[0].set_value("DD/MM/YYYY").run()
    assert not app.exception
    assert any("03 Apr 2025" in c.value for c in app.caption)
def test_upload_with_problems_reports_notes():
    messy = "\n".join([HEADER, GOOD_ROW, GOOD_ROW, "ORD-2,bad date,Europe,Germany,Laptop,Technology,Online,2,100,200,120,80"]).encode()
    app = upload(open_app(), "messy.csv", messy)
    assert not app.exception
    assert any("Data quality notes" in e.label for e in app.sidebar.expander)
    assert any("Loaded 1 of 3 rows" in s.value for s in app.sidebar.success)


@needs_data
@pytest.mark.parametrize("name, content", [
    ("empty.csv", b""),
    ("wrong_columns.csv", b"Name,Age\nAnna,30\n"),
    ("headers_only.csv", (HEADER + "\n").encode()),
    ("junk.csv", bytes(range(256)) * 20),
])
def test_invalid_upload_shows_error_and_dashboard_keeps_working(name, content):
    app = upload(open_app(), name, content)
    assert not app.exception                                # no raw traceback
    assert any("Upload rejected" in e.value for e in app.sidebar.error)
    assert len(app.metric) == 6                             # sample data still on screen