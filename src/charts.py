"""
charts.py
---------
One function per Plotly chart. Every function:
  * takes an already-filtered DataFrame,
  * returns a Plotly Figure (app.py decides where to show it),
  * returns a friendly "No data" figure instead of crashing if the DataFrame is empty.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.metrics import CURRENCY_SYMBOL

# ---------------------------------------------------------------
# Look and feel (change colours here and every chart follows)
# ---------------------------------------------------------------
BRAND = "#2E75B6"        # main blue
POSITIVE = "#2A9D8F"     # teal  - good / profit
NEGATIVE = "#D1495B"     # red   - bad / loss
COLORWAY = ["#1F4E79", "#2E75B6", "#2A9D8F", "#E9A23B", "#8E6BBF", "#6C757D"]
GRID = "rgba(128, 128, 128, 0.20)"
FONT = "Segoe UI, Arial, sans-serif"


# ---------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------
def _style(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    """Apply the same professional look to every chart."""
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16)),
        font=dict(family=FONT, size=12),
        margin=dict(l=10, r=40, t=55, b=10),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(font_family=FONT),
    )
    return fig


def _empty_figure(title: str) -> go.Figure:
    """A blank chart with a message, shown when the filters leave no data."""
    fig = go.Figure()
    fig.add_annotation(
        text="No data for the selected filters",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="gray"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, title)


def _money_axis(fig: go.Figure, axis: str) -> None:
    """Show axis numbers as $50k, $1.2M ..."""
    update = fig.update_xaxes if axis == "x" else fig.update_yaxes
    update(tickprefix=CURRENCY_SYMBOL, tickformat="~s", gridcolor=GRID, zeroline=False, title=None)


def _horizontal_bar(data: pd.DataFrame, label_col: str, title: str, color: str) -> go.Figure:
    """Horizontal bar chart of Revenue by `label_col`, largest bar on top."""
    fig = px.bar(data, x="Revenue", y=label_col, orientation="h", color_discrete_sequence=[color])
    fig.update_traces(
        texttemplate=CURRENCY_SYMBOL + "%{x:,.0f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Revenue: " + CURRENCY_SYMBOL + "%{x:,.2f}<extra></extra>",
    )
    fig.update_yaxes(title=None, categoryorder="total ascending")
    _money_axis(fig, "x")
    return _style(fig, title)


# ---------------------------------------------------------------
# The charts
# ---------------------------------------------------------------
def monthly_revenue_trend(df: pd.DataFrame) -> go.Figure:
    title = "Monthly Revenue Trend"
    if df.empty:
        return _empty_figure(title)

    month = df["Order_Date"].dt.to_period("M").dt.to_timestamp()      # 2025-03-17 -> 2025-03-01
    monthly = df.groupby(month)["Revenue"].sum()
    full_range = pd.date_range(monthly.index.min(), monthly.index.max(), freq="MS")
    monthly = monthly.reindex(full_range, fill_value=0)                # months with no sales show as 0

    fig = go.Figure(go.Scatter(
        x=monthly.index, y=monthly.values, mode="lines+markers",
        line=dict(color=BRAND, width=3), marker=dict(size=7),
        fill="tozeroy", fillcolor="rgba(46, 117, 182, 0.12)",
        hovertemplate="<b>%{x|%B %Y}</b><br>Revenue: " + CURRENCY_SYMBOL + "%{y:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(tickformat="%b %Y", showgrid=False, title=None)
    _money_axis(fig, "y")
    return _style(fig, title)


def revenue_by_region(df: pd.DataFrame) -> go.Figure:
    title = "Revenue by Region"
    if df.empty:
        return _empty_figure(title)
    data = df.groupby("Region", as_index=False)["Revenue"].sum()
    return _horizontal_bar(data, "Region", title, BRAND)


def revenue_by_channel(df: pd.DataFrame) -> go.Figure:
    title = "Revenue by Sales Channel"
    if df.empty:
        return _empty_figure(title)
    data = df.groupby("Sales_Channel", as_index=False)["Revenue"].sum()
    return _horizontal_bar(data, "Sales_Channel", title, COLORWAY[0])


def revenue_by_category(df: pd.DataFrame) -> go.Figure:
    title = "Revenue by Product Category"
    if df.empty:
        return _empty_figure(title)
    data = df.groupby("Category", as_index=False)["Revenue"].sum()
    fig = px.pie(data, names="Category", values="Revenue", hole=0.55, color_discrete_sequence=COLORWAY)
    fig.update_traces(
        textinfo="percent", textposition="inside", sort=True,
        hovertemplate="<b>%{label}</b><br>Revenue: " + CURRENCY_SYMBOL + "%{value:,.2f}<br>Share: %{percent}<extra></extra>",
    )
    _style(fig, title)
    fig.update_layout(showlegend=True, legend=dict(orientation="v", y=0.5))
    return fig


def top_products(df: pd.DataFrame, n: int = 5) -> go.Figure:
    title = f"Top {n} Products by Revenue"
    if df.empty:
        return _empty_figure(title)
    data = df.groupby("Product", as_index=False)["Revenue"].sum().nlargest(n, "Revenue")
    return _horizontal_bar(data, "Product", title, POSITIVE)


def bottom_products(df: pd.DataFrame, n: int = 5) -> go.Figure:
    title = f"Bottom {n} Products by Revenue"
    if df.empty:
        return _empty_figure(title)
    data = df.groupby("Product", as_index=False)["Revenue"].sum().nsmallest(n, "Revenue")
    return _horizontal_bar(data, "Product", title, NEGATIVE)


def profitability_by_category(df: pd.DataFrame) -> go.Figure:
    title = "Profit by Category (labels show profit margin %)"
    if df.empty:
        return _empty_figure(title)

    data = df.groupby("Category", as_index=False).agg(Revenue=("Revenue", "sum"), Profit=("Profit", "sum"))
    data["Margin"] = (data["Profit"] / data["Revenue"].replace(0, np.nan) * 100).fillna(0)
    data = data.sort_values("Profit", ascending=False)

    fig = go.Figure(go.Bar(
        x=data["Category"], y=data["Profit"],
        marker_color=[POSITIVE if p >= 0 else NEGATIVE for p in data["Profit"]],
        text=[f"{m:.1f}%" for m in data["Margin"]], textposition="outside", cliponaxis=False,
        customdata=np.stack([data["Revenue"], data["Margin"]], axis=-1),
        hovertemplate=(
            "<b>%{x}</b><br>Profit: " + CURRENCY_SYMBOL + "%{y:,.2f}"
            "<br>Revenue: " + CURRENCY_SYMBOL + "%{customdata[0]:,.2f}"
            "<br>Margin: %{customdata[1]:.1f}%<extra></extra>"
        ),
    ))
    fig.update_xaxes(title=None)
    _money_axis(fig, "y")
    return _style(fig, title)