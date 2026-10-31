"""Scratch script: builds every chart, checks the numbers, and writes charts_preview.html."""
import plotly.graph_objects as go
from src.charts import (
    bottom_products, monthly_revenue_trend, profitability_by_category,
    revenue_by_category, revenue_by_channel, revenue_by_region, top_products,
)
from src.data_loader import load_sales_data
from src.metrics import filter_by_date, filter_by_dimensions

df, _ = load_sales_data("data/sales_data.csv")
total_revenue = df["Revenue"].sum()

# --- 1. Build all charts on the full dataset ---------------------------
figures = {
    "trend": monthly_revenue_trend(df),
    "region": revenue_by_region(df),
    "category": revenue_by_category(df),
    "channel": revenue_by_channel(df),
    "top5": top_products(df),
    "bottom5": bottom_products(df),
    "profit": profitability_by_category(df),
}
assert all(isinstance(f, go.Figure) for f in figures.values())

# --- 2. Check that chart numbers agree with plain Pandas ----------------
assert abs(sum(figures["trend"].data[0].y) - total_revenue) < 0.01
assert abs(sum(figures["region"].data[0].x) - total_revenue) < 0.01
assert abs(sum(figures["channel"].data[0].x) - total_revenue) < 0.01
assert abs(sum(figures["category"].data[0].values) - total_revenue) < 0.01
assert abs(sum(figures["profit"].data[0].y) - df["Profit"].sum()) < 0.01
by_product = df.groupby("Product")["Revenue"].sum().sort_values()
assert list(figures["top5"].data[0].y) == list(by_product.nlargest(5).index)
assert list(figures["bottom5"].data[0].y) == list(by_product.nsmallest(5).index)
print("Chart numbers match Pandas.")

# --- 3. Charts react to filters ------------------------------------------
subset = filter_by_date(filter_by_dimensions(df, regions=["Europe"]), "2025-01-01", "2025-06-30")
trend = monthly_revenue_trend(subset)
print("Europe, Jan-Jun 2025 -> trend has", len(trend.data[0].x), "months")
assert len(trend.data[0].x) <= 6
assert abs(sum(revenue_by_region(subset).data[0].x) - subset["Revenue"].sum()) < 0.01

# --- 4. Empty data must not crash -----------------------------------------
empty = filter_by_dimensions(df, regions=[])
for name, func in [("trend", monthly_revenue_trend), ("region", revenue_by_region),
                   ("category", revenue_by_category), ("channel", revenue_by_channel),
                   ("top5", top_products), ("bottom5", bottom_products),
                   ("profit", profitability_by_category)]:
    assert isinstance(func(empty), go.Figure), name
print("Empty-data charts OK.")

# --- 5. Write a preview page you can open in your browser ------------------
html = "<html><head><title>Charts preview</title></head><body style='font-family:Segoe UI;max-width:1000px;margin:auto'>"
for i, fig in enumerate(figures.values()):
    html += fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False)
html += "</body></html>"
with open("charts_preview.html", "w", encoding="utf-8") as f:
    f.write(html)
print("Wrote charts_preview.html - open it in your browser.")
print("\nAll checks passed.")