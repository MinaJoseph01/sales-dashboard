"""
generate_data.py
----------------
Creates a realistic SYNTHETIC (fictional) sales dataset and saves it to
data/sales_data.csv.

Calculation rules (documented in the README too):
    Revenue = Quantity x Unit_Price
    Cost    = TOTAL cost of the whole order line (not per unit)
    Profit  = Revenue - Cost

Run it from the project folder:
    python generate_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------
# 1. SETTINGS - change these to get a bigger/smaller dataset
# ---------------------------------------------------------------
SEED = 42                      # same seed = same "random" data every time
N_ORDERS = 1200                # each order has 1-4 lines, so rows will be ~2x this
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"
OUTPUT_PATH = Path("data") / "sales_data.csv"

# ---------------------------------------------------------------
# 2. REFERENCE DATA (dictionaries and lists describing our "business")
# ---------------------------------------------------------------
REGION_COUNTRIES = {
    "North America": ["United States", "Canada"],
    "Europe": ["United Kingdom", "Germany", "France"],
    "Middle East": ["United Arab Emirates", "Saudi Arabia"],
    "Asia Pacific": ["India", "Australia", "Japan"],
}
REGION_WEIGHTS = [0.35, 0.28, 0.17, 0.20]      # share of orders per region (sums to 1)

CHANNELS = ["Online", "Retail Store", "Distributor", "Mobile App"]
CHANNEL_WEIGHTS = [0.42, 0.28, 0.18, 0.12]

# category -> list of (product, typical unit price, (min cost ratio, max cost ratio))
# cost ratio = cost / revenue, so 0.70 means a 30% margin
PRODUCTS = {
    "Technology": [
        ("Laptop Pro 15", 1250.00, (0.72, 0.84)),
        ("Wireless Headphones", 180.00, (0.55, 0.70)),
        ("4K Monitor", 420.00, (0.70, 0.82)),
        ("Mechanical Keyboard", 95.00, (0.50, 0.65)),
        ("Smartphone X", 899.00, (0.75, 0.86)),
    ],
    "Furniture": [
        ("Ergonomic Chair", 340.00, (0.68, 0.82)),
        ("Standing Desk", 560.00, (0.70, 0.85)),
        ("Bookcase", 210.00, (0.72, 0.88)),
        ("Conference Table", 1100.00, (0.78, 0.92)),
    ],
    "Office Supplies": [
        ("Printer Paper (Box)", 32.00, (0.55, 0.70)),
        ("Ink Cartridge", 58.00, (0.50, 0.66)),
        ("Notebook Set", 14.00, (0.40, 0.58)),
        ("Desk Organizer", 26.00, (0.45, 0.62)),
        ("Whiteboard", 75.00, (0.55, 0.70)),
    ],
    "Accessories": [
        ("USB-C Hub", 49.00, (0.45, 0.60)),
        ("Laptop Bag", 65.00, (0.50, 0.65)),
        ("Webcam HD", 79.00, (0.52, 0.68)),
        ("Wireless Mouse", 35.00, (0.42, 0.58)),
    ],
}
CATEGORY_NAMES = list(PRODUCTS.keys())
CATEGORY_WEIGHTS = [0.25, 0.15, 0.35, 0.25]

# Busier months get a higher weight (Q4 holiday peak, quieter summer)
MONTH_WEIGHTS = {1: 0.85, 2: 0.80, 3: 0.95, 4: 0.95, 5: 1.00, 6: 0.95,
                 7: 0.90, 8: 0.90, 9: 1.00, 10: 1.10, 11: 1.30, 12: 1.40}


# ---------------------------------------------------------------
# 3. FUNCTIONS
# ---------------------------------------------------------------
def make_order_dates(rng: np.random.Generator, n_orders: int) -> np.ndarray:
    """Pick a date for each order, with seasonality and gentle growth over time."""
    all_days = pd.date_range(START_DATE, END_DATE, freq="D")
    seasonal = np.array([MONTH_WEIGHTS[d.month] for d in all_days])
    growth = np.linspace(1.0, 1.4, len(all_days))        # +40% busier by the end
    weights = seasonal * growth
    weights = weights / weights.sum()                    # probabilities must sum to 1
    chosen = rng.choice(all_days.to_numpy(), size=n_orders, p=weights)
    return np.sort(chosen)                               # sorted, so Order_IDs rise with date


def generate_sales_data(seed: int = SEED, n_orders: int = N_ORDERS) -> pd.DataFrame:
    """Build the full dataset and return it as a DataFrame."""
    rng = np.random.default_rng(seed)
    order_dates = make_order_dates(rng, n_orders)

    rows = []  # we collect one dictionary per order line, then convert to a DataFrame
    for i in range(n_orders):
        order_id = f"ORD-{100001 + i}"
        order_date = order_dates[i]

        # These belong to the whole order, so every line in it shares them
        region = rng.choice(list(REGION_COUNTRIES.keys()), p=REGION_WEIGHTS)
        country = rng.choice(REGION_COUNTRIES[region])
        channel = rng.choice(CHANNELS, p=CHANNEL_WEIGHTS)

        n_lines = rng.choice([1, 2, 3, 4], p=[0.45, 0.30, 0.17, 0.08])
        for _ in range(n_lines):
            category = rng.choice(CATEGORY_NAMES, p=CATEGORY_WEIGHTS)
            product, base_price, (cost_low, cost_high) = PRODUCTS[category][
                rng.integers(len(PRODUCTS[category]))
            ]

            unit_price = round(base_price * rng.uniform(0.90, 1.10), 2)
            max_qty = 3 if base_price > 500 else 10          # expensive items sell in smaller quantities
            quantity = int(rng.integers(1, max_qty + 1))

            revenue = round(quantity * unit_price, 2)
            if rng.random() < 0.04:                          # ~4% of lines are loss-making (heavy discounts)
                cost = round(revenue * rng.uniform(1.05, 1.30), 2)
            else:
                cost = round(revenue * rng.uniform(cost_low, cost_high), 2)
            profit = round(revenue - cost, 2)

            rows.append({
                "Order_ID": order_id,
                "Order_Date": pd.Timestamp(order_date).strftime("%Y-%m-%d"),
                "Region": region,
                "Country": country,
                "Product": product,
                "Category": category,
                "Sales_Channel": channel,
                "Quantity": quantity,
                "Unit_Price": unit_price,
                "Revenue": revenue,
                "Cost": cost,
                "Profit": profit,
            })

    return pd.DataFrame(rows)


def check_data(df: pd.DataFrame) -> None:
    """Fail loudly if the calculation rules are broken."""
    assert np.allclose(df["Revenue"], df["Quantity"] * df["Unit_Price"], atol=0.01), "Revenue rule broken"
    assert np.allclose(df["Profit"], df["Revenue"] - df["Cost"], atol=0.01), "Profit rule broken"
    assert not df.isna().any().any(), "Unexpected missing values"
    assert not df.duplicated().any(), "Unexpected duplicate rows"


def main() -> None:
    df = generate_sales_data()
    check_data(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    total_revenue = df["Revenue"].sum()
    total_profit = df["Profit"].sum()
    print(f"Saved {len(df):,} rows to {OUTPUT_PATH}")
    print(f"Unique orders : {df['Order_ID'].nunique():,}")
    print(f"Date range    : {df['Order_Date'].min()} to {df['Order_Date'].max()}")
    print(f"Total revenue : {total_revenue:,.2f}")
    print(f"Total profit  : {total_profit:,.2f}")
    print(f"Profit margin : {total_profit / total_revenue:.1%}")
    print("All calculation checks passed.")


if __name__ == "__main__":
    main()