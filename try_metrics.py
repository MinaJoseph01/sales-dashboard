"""Scratch script: checks metrics.py against independent calculations. Safe to delete later."""
import pandas as pd
from src.data_loader import load_sales_data
from src.metrics import (
    calculate_kpis, compare_kpis, filter_by_date, filter_by_dimensions,
    format_change, format_value, get_previous_period, has_full_previous_period,
    percent_change,
)

df, _ = load_sales_data("data/sales_data.csv")

# --- 1. Whole-dataset KPIs, compared with plain Pandas ---------------
k = calculate_kpis(df)
print("ALL DATA:", k)
assert round(k["total_revenue"], 2) == round(df["Revenue"].sum(), 2)
assert k["total_orders"] == df["Order_ID"].nunique() == 1200
assert k["units_sold"] == df["Quantity"].sum()
assert abs(k["aov"] - k["total_revenue"] / 1200) < 1e-9
assert abs(k["profit_margin"] - k["total_profit"] / k["total_revenue"] * 100) < 1e-9
print("KPI checks passed\n")

# --- 2. Previous period ----------------------------------------------
start, end = "2025-01-01", "2025-03-31"
prev_start, prev_end = get_previous_period(start, end)
print(f"Selected 2025-01-01..2025-03-31 -> previous {prev_start.date()}..{prev_end.date()}")
assert (prev_end - prev_start).days == (pd.Timestamp(end) - pd.Timestamp(start)).days

# --- 3. Filters and comparison cards ---------------------------------
base = filter_by_dimensions(df, regions=["Europe"])
current = filter_by_date(base, start, end)
previous = filter_by_date(base, prev_start, prev_end)
print("Europe rows: current", len(current), "| previous", len(previous))
assert (current["Region"] == "Europe").all()
assert current["Order_Date"].between(start, end).all()
print("Full previous period available?", has_full_previous_period(df, prev_start))

for card in compare_kpis(current, previous):
    print(f"  {card.label:16} {format_value(card.value, card.kind):>10}   vs prev {format_change(card.change, card.kind)}")

# --- 4. Edge cases ----------------------------------------------------
empty = filter_by_dimensions(df, regions=[])
print("\nEmpty selection ->", len(empty), "rows; KPIs:", calculate_kpis(empty))
assert percent_change(100, 0) is None
first_year = filter_by_date(df, "2024-01-01", "2024-03-31")
p_start, p_end = get_previous_period("2024-01-01", "2024-03-31")
cards = compare_kpis(first_year, filter_by_date(df, p_start, p_end))
print("First quarter of data -> change shown as:", format_change(cards[0].change, cards[0].kind))
print("Full previous period available?", has_full_previous_period(df, p_start))
print("\nAll checks passed.")