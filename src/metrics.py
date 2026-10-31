"""
metrics.py
----------
All KPI calculations and filtering helpers. Nothing here is hardcoded:
every number is calculated from whatever DataFrame it is given.

Definitions (also documented in the README):
    Total Revenue  = sum of Revenue
    Total Orders   = number of UNIQUE Order_IDs
    Units Sold     = sum of Quantity
    AOV            = Total Revenue / Total Orders
    Total Profit   = sum of Profit
    Profit Margin  = Total Profit / Total Revenue x 100

Previous period = a window of the same length that ends the day before the
selected start date. Example: 1 Jan - 31 Mar 2025 (90 days) is compared with
3 Oct - 31 Dec 2024 (90 days).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

CURRENCY_SYMBOL = "$"  # change this one line to switch the dashboard currency symbol


# ---------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------
def filter_by_date(df: pd.DataFrame, start, end) -> pd.DataFrame:
    """Keep rows whose Order_Date is between start and end (both inclusive)."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    return df[(df["Order_Date"] >= start) & (df["Order_Date"] <= end)]


def filter_by_dimensions(df: pd.DataFrame, regions=None, categories=None, channels=None) -> pd.DataFrame:
    """Filter by Region, Category and Sales_Channel.

    None  -> do not filter on that column (keep everything).
    list  -> keep only the listed values. An EMPTY list keeps nothing.
    """
    if regions is not None:
        df = df[df["Region"].isin(regions)]
    if categories is not None:
        df = df[df["Category"].isin(categories)]
    if channels is not None:
        df = df[df["Sales_Channel"].isin(channels)]
    return df


# ---------------------------------------------------------------
# Previous-period logic
# ---------------------------------------------------------------
def get_previous_period(start, end) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return (prev_start, prev_end): the same number of days, immediately before `start`."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    n_days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=n_days - 1)
    return prev_start, prev_end


def has_full_previous_period(df: pd.DataFrame, prev_start) -> bool:
    """True if the dataset reaches back far enough to cover the whole previous period."""
    if df.empty:
        return False
    return df["Order_Date"].min() <= pd.Timestamp(prev_start)


# ---------------------------------------------------------------
# KPI calculations
# ---------------------------------------------------------------
def safe_divide(numerator: float, denominator: float) -> float:
    """Divide, but return 0 instead of crashing when the denominator is 0."""
    return numerator / denominator if denominator else 0.0


def calculate_kpis(df: pd.DataFrame) -> dict[str, float]:
    """Calculate the six headline KPIs for a DataFrame (works on an empty one too)."""
    total_revenue = float(df["Revenue"].sum())
    total_profit = float(df["Profit"].sum())
    total_orders = int(df["Order_ID"].nunique())
    return {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "units_sold": int(df["Quantity"].sum()),
        "aov": safe_divide(total_revenue, total_orders),
        "total_profit": total_profit,
        "profit_margin": safe_divide(total_profit, total_revenue) * 100,
    }


def percent_change(current: float, previous: float) -> float | None:
    """Percent change vs previous. Returns None when previous is 0 (change is undefined)."""
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


@dataclass
class KpiResult:
    """One KPI card: the value, the previous-period value, and the change."""
    label: str
    value: float
    previous: float
    change: float | None   # % change; for margin it is percentage POINTS
    kind: str              # "currency", "number" or "percent" (controls formatting)


# (key in calculate_kpis, card label, kind) - this list controls card order
KPI_LAYOUT = [
    ("total_revenue", "Total Revenue", "currency"),
    ("total_orders", "Total Orders", "number"),
    ("units_sold", "Units Sold", "number"),
    ("aov", "Avg Order Value", "currency"),
    ("total_profit", "Total Profit", "currency"),
    ("profit_margin", "Profit Margin", "percent"),
]


def compare_kpis(current_df: pd.DataFrame, previous_df: pd.DataFrame) -> list[KpiResult]:
    """Calculate KPIs for both periods and return the six cards, ready to display."""
    current = calculate_kpis(current_df)
    previous = calculate_kpis(previous_df)
    has_previous = not previous_df.empty

    results = []
    for key, label, kind in KPI_LAYOUT:
        if not has_previous:
            change = None
        elif kind == "percent":
            change = current[key] - previous[key]          # percentage points
        else:
            change = percent_change(current[key], previous[key])
        results.append(KpiResult(label, current[key], previous[key], change, kind))
    return results


# ---------------------------------------------------------------
# Display helpers (turn numbers into text for the KPI cards)
# ---------------------------------------------------------------
def format_value(value: float, kind: str) -> str:
    """Format a KPI value: $1.75M, 1,200, 25.4% ..."""
    if kind == "percent":
        return f"{value:.1f}%"
    if kind == "number":
        return f"{value:,.0f}"
    # currency
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{CURRENCY_SYMBOL}{value / 1_000_000:,.2f}M"
    if magnitude >= 10_000:
        return f"{CURRENCY_SYMBOL}{value / 1_000:,.1f}K"
    return f"{CURRENCY_SYMBOL}{value:,.2f}"


def format_change(change: float | None, kind: str) -> str:
    """Format the change vs previous period: '+12.3%', '-1.4 pp', or 'n/a'."""
    if change is None:
        return "n/a"
    if kind == "percent":
        return f"{change:+.1f} pp"   # pp = percentage points
    return f"{change:+.1f}%"