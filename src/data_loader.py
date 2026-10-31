"""
data_loader.py
--------------
Reads a sales CSV, checks it, cleans it, and returns a tidy DataFrame
plus a short report of what was fixed or removed.

This module does NOT import Streamlit. That keeps it easy to test on its own;
app.py will call it and show the messages in the browser.

Cleaning rules (also documented in the README):
  1. Column names are matched ignoring case/spaces ("order date" -> Order_Date).
  2. Dates are parsed automatically; numbers are converted (currency symbols
     and thousands separators are stripped).
  3. Rows are REMOVED if they are exact duplicates, or if Order_ID, Order_Date,
     Quantity, Unit_Price or Cost is missing/invalid, or Quantity <= 0,
     or Unit_Price < 0.
  4. Missing Region/Country/Product/Category/Sales_Channel -> "Unknown".
  5. Missing Revenue  -> Quantity x Unit_Price.
     Missing Profit   -> Revenue - Cost.
     Existing Revenue/Profit values that disagree with the formulas are kept,
     but reported as a warning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# ---------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------
REQUIRED_COLUMNS = [
    "Order_ID", "Order_Date", "Region", "Country", "Product", "Category",
    "Sales_Channel", "Quantity", "Unit_Price", "Revenue", "Cost", "Profit",
]
NUMERIC_COLUMNS = ["Quantity", "Unit_Price", "Revenue", "Cost", "Profit"]
FILLABLE_TEXT_COLUMNS = ["Region", "Country", "Product", "Category", "Sales_Channel"]
CRITICAL_COLUMNS = ["Order_ID", "Order_Date", "Quantity", "Unit_Price", "Cost"]

TOLERANCE = 0.01  # allowed rounding difference when checking Revenue/Profit


class DataValidationError(Exception):
    """Raised when a file can't be used. The message is safe to show to the user."""


@dataclass
class LoadReport:
    """What happened while loading: row counts and a list of plain-English notes."""
    rows_read: int = 0
    rows_kept: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def rows_removed(self) -> int:
        return self.rows_read - self.rows_kept


# ---------------------------------------------------------------
# Step A: read the file
# ---------------------------------------------------------------
def read_csv_file(source) -> pd.DataFrame:
    """Read a CSV from a file path OR an uploaded file object.

    Tries UTF-8 first (the normal case), then Latin-1 (common for Excel exports).
    """
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            if hasattr(source, "seek"):
                source.seek(0)  # rewind an uploaded file before each attempt
            return pd.read_csv(source, encoding=encoding)
        except UnicodeDecodeError:
            continue
        except FileNotFoundError as exc:
            raise DataValidationError(f"File not found: {source}") from exc
        except pd.errors.EmptyDataError as exc:
            raise DataValidationError("The file is empty. Please upload a CSV that contains data.") from exc
        except pd.errors.ParserError as exc:
            raise DataValidationError(
                "The file could not be read as a CSV. Check that it is a plain .csv file "
                f"(not Excel) with consistent columns. Details: {exc}"
            ) from exc
    raise DataValidationError("The file's text encoding could not be recognised.")


# ---------------------------------------------------------------
# Step B: check the columns
# ---------------------------------------------------------------
def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns like 'order date' or 'ORDER_DATE' to the official 'Order_Date'."""
    official = {name.lower(): name for name in REQUIRED_COLUMNS}
    renames = {}
    for col in df.columns:
        key = str(col).strip().lower().replace(" ", "_").replace("-", "_")
        if key in official:
            renames[col] = official[key]
    return df.rename(columns=renames)


def validate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Make sure every required column exists. Extra columns are ignored."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise DataValidationError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Columns found in your file: {', '.join(map(str, df.columns))}. "
            "Please use the sample template as a guide."
        )
    return df[REQUIRED_COLUMNS].copy()


# ---------------------------------------------------------------
# Step C: clean the data
# ---------------------------------------------------------------
def _to_number(series: pd.Series) -> pd.Series:
    """Convert to numbers. Text like '$1,250.50' becomes 1250.5; junk becomes NaN."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = series.astype(str).str.replace(r"[^0-9.\-]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")

def _parse_dates(series: pd.Series, dayfirst: bool) -> pd.Series:
    """Parse dates safely.

    Step 1: anything written as ISO (2025-01-31) is read exactly as written.
    Step 2: whatever is left (03/04/2025, Jan 16 2025 ...) is read with `dayfirst`.
    Doing ISO first matters: with dayfirst=True, Pandas would misread 2025-01-05 as 1 May.
    """
    text = series.astype("string").str.strip()
    parsed = pd.to_datetime(text, errors="coerce", format="ISO8601")
    others = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=dayfirst)
    return parsed.fillna(others).dt.normalize()


def clean_data(df: pd.DataFrame, dayfirst: bool = False) -> tuple[pd.DataFrame, LoadReport]:
    """Clean a DataFrame that already has the required columns."""
    report = LoadReport(rows_read=len(df))
    notes = report.notes
    df = df.copy()

    # 1. Text columns: trim spaces, treat empty text as missing
    for col in ["Order_ID"] + FILLABLE_TEXT_COLUMNS:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)

    # 2. Dates: parse automatically; anything unreadable becomes NaT (missing date)
    missing_before = df["Order_Date"].isna().sum()
    df["Order_Date"] = _parse_dates(df["Order_Date"], dayfirst)
    bad_dates = df["Order_Date"].isna().sum() - missing_before
    if bad_dates:
        notes.append(f"{bad_dates:,} value(s) in 'Order_Date' could not be read as dates.")

    # 3. Numbers: convert and count anything that wasn't a valid number
    for col in NUMERIC_COLUMNS:
        missing_before = df[col].isna().sum()
        df[col] = _to_number(df[col])
        bad_numbers = df[col].isna().sum() - missing_before
        if bad_numbers:
            notes.append(f"{bad_numbers:,} value(s) in '{col}' were not valid numbers.")

    # 4. Remove exact duplicate rows
    duplicates = int(df.duplicated().sum())
    if duplicates:
        df = df.drop_duplicates()
        notes.append(f"Removed {duplicates:,} duplicate row(s).")

    # 5. Remove rows missing a critical field
    critical_missing = df[CRITICAL_COLUMNS].isna().any(axis=1)
    if critical_missing.any():
        notes.append(
            f"Removed {int(critical_missing.sum()):,} row(s) missing Order_ID, Order_Date, "
            "Quantity, Unit_Price or Cost."
        )
        df = df[~critical_missing]

    # 6. Remove rows with impossible values
    invalid = (df["Quantity"] <= 0) | (df["Unit_Price"] < 0)
    if invalid.any():
        notes.append(f"Removed {int(invalid.sum()):,} row(s) with Quantity <= 0 or negative Unit_Price.")
        df = df[~invalid]

    # 7. Fill missing descriptive text with "Unknown"
    for col in FILLABLE_TEXT_COLUMNS:
        n_missing = int(df[col].isna().sum())
        if n_missing:
            notes.append(f"Filled {n_missing:,} missing value(s) in '{col}' with 'Unknown'.")
            df[col] = df[col].fillna("Unknown")

    if df.empty:
        raise DataValidationError(
            "No valid rows remain after cleaning. Details: " + " ".join(notes)
        )

    # 8. Derive missing Revenue / Profit, and warn if existing values disagree with the formulas
    expected_revenue = df["Quantity"] * df["Unit_Price"]
    n_filled = int(df["Revenue"].isna().sum())
    if n_filled:
        df["Revenue"] = df["Revenue"].fillna(expected_revenue)
        notes.append(f"Calculated {n_filled:,} missing Revenue value(s) as Quantity x Unit_Price.")
    n_mismatch = int(((df["Revenue"] - expected_revenue).abs() > TOLERANCE).sum())
    if n_mismatch:
        notes.append(f"Warning: {n_mismatch:,} row(s) have Revenue different from Quantity x Unit_Price (kept as provided).")

    expected_profit = df["Revenue"] - df["Cost"]
    n_filled = int(df["Profit"].isna().sum())
    if n_filled:
        df["Profit"] = df["Profit"].fillna(expected_profit)
        notes.append(f"Calculated {n_filled:,} missing Profit value(s) as Revenue - Cost.")
    n_mismatch = int(((df["Profit"] - expected_profit).abs() > TOLERANCE).sum())
    if n_mismatch:
        notes.append(f"Warning: {n_mismatch:,} row(s) have Profit different from Revenue - Cost (kept as provided).")

    # 9. Final tidy-up: plain text types, whole-number quantities, sorted by date
    for col in ["Order_ID"] + FILLABLE_TEXT_COLUMNS:
        df[col] = df[col].astype(str)
    if (df["Quantity"] % 1 == 0).all():
        df["Quantity"] = df["Quantity"].astype("int64")
    df = df.sort_values(["Order_Date", "Order_ID"]).reset_index(drop=True)

    report.rows_kept = len(df)
    return df, report


# ---------------------------------------------------------------
# The one function the dashboard will call
# ---------------------------------------------------------------
def load_sales_data(source, dayfirst: bool = False) -> tuple[pd.DataFrame, LoadReport]:
    """Read, validate and clean a sales CSV (file path or uploaded file)."""
    raw = read_csv_file(source)
    if raw.empty:
        raise DataValidationError("The file has column headings but no data rows.")
    raw = standardize_columns(raw)
    raw = validate_columns(raw)
    return clean_data(raw, dayfirst)