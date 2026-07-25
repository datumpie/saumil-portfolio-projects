"""
breakfast_index.py
The True Breakfast Commodity Index
----------------------------------------------------------------------------
Pulls live historical retail price data for six breakfast staples (bacon,
eggs, milk, bread, coffee, potatoes) from the Federal Reserve Economic Data
(FRED) system, builds a weighted composite "Breakfast Index," and compares
its inflation rate against Headline and Core CPI. Results are stored in a
local SQLite database that can be connected directly to Power BI.

Project: Datum Pie / Stackend Solutions Portfolio -- Project 2
Author:  Saumil Chokshi
----------------------------------------------------------------------------
HOW TO RUN THIS (non-technical, copy/paste steps):
    1. Install Python 3.10 or newer from https://www.python.org/downloads/
    2. Open a terminal (Command Prompt on Windows, Terminal on Mac) in this
       project folder.
    3. Run:  pip install -r requirements.txt
    4. (Optional) Edit the USER CONFIGURATION section below to change the
       date range.
    5. Run:  python breakfast_index.py
    6. Read the printed summary, or open breakfast_index.db in Power BI
       (see docs/power-bi-setup.md for click-by-click steps).
----------------------------------------------------------------------------
"""

import sqlite3
import sys

try:
    import pandas as pd
except ImportError:
    print("ERROR: The 'pandas' package is not installed.")
    print("Run this command first, then try again:")
    print("    pip install -r requirements.txt")
    sys.exit(1)

try:
    import pandas_datareader.data as web
except ImportError:
    print("ERROR: The 'pandas-datareader' package is not installed.")
    print("Run this command first, then try again:")
    print("    pip install -r requirements.txt")
    sys.exit(1)


# ============================================================================
# USER CONFIGURATION -- edit these values, then run the script.
# No other part of this file needs to change for normal use.
# ============================================================================

# How far back to pull price history. FRED's APU (Average Price) series for
# these items generally start in the late 1970s through the 1990s
# depending on the item; 2005 onward keeps the chart readable and covers
# two full inflation cycles (2008 and 2021-2023).
START_DATE = "2005-01-01"
END_DATE = None  # None = pull through the most recent available month

DB_PATH = "breakfast_index.db"

# ============================================================================
# THE BREAKFAST BASKET
# FRED series IDs for retail average prices, sourced from the U.S. Bureau
# of Labor Statistics' Average Price Data program. Verified directly
# against fred.stlouisfed.org as of July 2026.
# ============================================================================

FRED_SERIES = {
    # item_name: (FRED series ID, unit description)
    "Bacon": ("APU0000704111", "$ per lb"),
    "Eggs": ("APU0000708111", "$ per dozen"),
    "Milk": ("APU0000709112", "$ per gallon"),
    "Bread": ("APU0000702111", "$ per lb"),
    "Coffee": ("APU0000717311", "$ per lb"),
    "Potatoes": ("APU0000712112", "$ per lb"),
}

CPI_SERIES = {
    "Headline CPI": "CPIAUCSL",
    "Core CPI": "CPILFESL",
}

# ============================================================================
# INDEX WEIGHTS
# These are analyst-assigned weights reflecting a typical basic breakfast
# basket's rough expenditure share -- NOT official BLS relative-importance
# weights. This is a deliberate, documented simplification; see the
# Decision Log in README.md for why, and see "What assumptions are we
# making?" for the caveat this creates.
#
# Weights must sum to 1.0. The script checks this on every run.
# ============================================================================

ITEM_WEIGHTS = {
    "Bacon": 0.20,
    "Eggs": 0.20,
    "Bread": 0.15,
    "Milk": 0.15,
    "Coffee": 0.20,
    "Potatoes": 0.10,
}


# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_database(db_path):
    """Create (or reset) the SQLite database and its three tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS item_prices;
        DROP TABLE IF EXISTS composite_index;
        DROP TABLE IF EXISTS cpi_benchmark;

        CREATE TABLE item_prices (
            date          TEXT NOT NULL,
            item_name     TEXT NOT NULL,
            series_id     TEXT NOT NULL,
            unit          TEXT NOT NULL,
            raw_price     REAL,
            price_index   REAL,
            PRIMARY KEY (date, item_name)
        );

        CREATE TABLE composite_index (
            date               TEXT PRIMARY KEY,
            breakfast_index    REAL,
            breakfast_yoy_pct  REAL
        );

        CREATE TABLE cpi_benchmark (
            date                TEXT PRIMARY KEY,
            cpi_headline        REAL,
            cpi_headline_yoy_pct REAL,
            cpi_core            REAL,
            cpi_core_yoy_pct    REAL
        );
    """)
    conn.commit()
    return conn


# ============================================================================
# LIVE FRED DATA
# ============================================================================

def fetch_fred_series(series_ids, start_date, end_date):
    """
    Pull one or more FRED series via pandas-datareader. Returns a DataFrame
    indexed by date, with one column per series ID.

    No API key is required for this method -- pandas-datareader reads
    FRED's public CSV export endpoint directly. If FRED ever locks this
    endpoint down (as has happened with some other free data sources),
    see README.md's "Deployment, Maintenance" section for the fallback
    plan using the official `fredapi` package and a free API key.
    """
    raw = web.DataReader(series_ids, "fred", start_date, end_date)
    raw.index.name = "date"
    return raw


def clean_and_align(raw_df):
    """
    BLS Average Price series occasionally have a missing month (data
    collection gaps, methodology changes). Forward-fill any gaps so the
    index calculation never breaks on a NaN, and report exactly what was
    filled so nothing is silently changed.
    """
    missing_counts = raw_df.isna().sum()
    for series_id, count in missing_counts.items():
        if count > 0:
            print(f"NOTE: {series_id} had {count} missing month(s) -- "
                  f"forward-filled from the prior month's value.")
    return raw_df.ffill()


# ============================================================================
# INDEX CALCULATION
# ============================================================================

def build_item_price_index(raw_prices_df, series_to_item):
    """
    Convert each item's raw dollar price into a price INDEX, rebased to
    100 at the first available month in the pulled date range. This is
    what makes it valid to combine bacon ($/lb), eggs ($/dozen), and milk
    ($/gallon) in a single composite -- see the Decision Log in README.md
    for why raw dollar averaging across mismatched units would be
    meaningless.

    Returns a DataFrame with one column per item name (not series ID).
    """
    index_df = pd.DataFrame(index=raw_prices_df.index)
    for series_id, item_name in series_to_item.items():
        base_price = raw_prices_df[series_id].iloc[0]
        index_df[item_name] = (raw_prices_df[series_id] / base_price) * 100
    return index_df


def build_composite_index(item_index_df, weights):
    """
    Weighted sum of the individual item indices. Each item's contribution
    to the composite is proportional to its assigned weight in
    ITEM_WEIGHTS, not just a plain average -- see the Decision Log for why.
    """
    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > 0.001:
        raise ValueError(
            f"ITEM_WEIGHTS must sum to 1.0, but currently sums to "
            f"{total_weight}. Fix the weights before running the index."
        )

    composite = pd.Series(0.0, index=item_index_df.index)
    for item_name, weight in weights.items():
        composite += item_index_df[item_name] * weight
    composite.name = "breakfast_index"
    return composite


def compute_yoy_pct_change(series):
    """
    Year-over-year percent change, using a 12-month lag since this is
    monthly data. The first 12 months of any series will be NaN -- there's
    no prior year to compare against yet, which is expected and normal.
    """
    return series.pct_change(periods=12) * 100


# ============================================================================
# PERSISTENCE
# ============================================================================

def store_item_prices(conn, raw_prices_df, item_index_df, series_to_item, units):
    cur = conn.cursor()
    for series_id, item_name in series_to_item.items():
        unit = units[item_name]
        for date, raw_price in raw_prices_df[series_id].items():
            price_index = item_index_df.loc[date, item_name]
            cur.execute(
                """INSERT OR REPLACE INTO item_prices
                   (date, item_name, series_id, unit, raw_price, price_index)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date.strftime("%Y-%m-%d"), item_name, series_id, unit,
                 float(raw_price), float(price_index)),
            )
    conn.commit()


def store_composite_index(conn, composite_series, yoy_series):
    cur = conn.cursor()
    for date in composite_series.index:
        value = composite_series.loc[date]
        yoy = yoy_series.loc[date]
        cur.execute(
            """INSERT OR REPLACE INTO composite_index
               (date, breakfast_index, breakfast_yoy_pct)
               VALUES (?, ?, ?)""",
            (date.strftime("%Y-%m-%d"), float(value),
             None if pd.isna(yoy) else float(yoy)),
        )
    conn.commit()


def store_cpi_benchmark(conn, cpi_df, headline_yoy, core_yoy):
    cur = conn.cursor()
    for date in cpi_df.index:
        headline = cpi_df.loc[date, "CPIAUCSL"]
        core = cpi_df.loc[date, "CPILFESL"]
        h_yoy = headline_yoy.loc[date]
        c_yoy = core_yoy.loc[date]
        cur.execute(
            """INSERT OR REPLACE INTO cpi_benchmark
               (date, cpi_headline, cpi_headline_yoy_pct, cpi_core, cpi_core_yoy_pct)
               VALUES (?, ?, ?, ?, ?)""",
            (date.strftime("%Y-%m-%d"),
             float(headline), None if pd.isna(h_yoy) else float(h_yoy),
             float(core), None if pd.isna(c_yoy) else float(c_yoy)),
        )
    conn.commit()


# ============================================================================
# OUTPUT
# ============================================================================

def print_summary(composite_yoy, headline_yoy, core_yoy):
    print("\n" + "=" * 60)
    print("THE TRUE BREAKFAST COMMODITY INDEX")
    print("=" * 60)

    latest_date = composite_yoy.dropna().index[-1]
    latest_breakfast = composite_yoy.dropna().iloc[-1]
    latest_headline = headline_yoy.loc[latest_date]
    latest_core = core_yoy.loc[latest_date]

    print(f"\nMost recent month: {latest_date.strftime('%B %Y')}\n")
    print(f"   Breakfast Index inflation (YoY): {latest_breakfast:+.1f}%")
    print(f"   Headline CPI inflation (YoY):    {latest_headline:+.1f}%")
    print(f"   Core CPI inflation (YoY):        {latest_core:+.1f}%")

    gap = latest_breakfast - latest_headline
    direction = "running HOTTER than" if gap > 0 else "running COOLER than"
    print(f"\n   Breakfast is currently {direction} headline inflation "
          f"by {abs(gap):.1f} percentage points.")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("Building the True Breakfast Commodity Index...\n")

    series_to_item = {series_id: item_name
                       for item_name, (series_id, unit) in FRED_SERIES.items()}
    units = {item_name: unit for item_name, (series_id, unit) in FRED_SERIES.items()}
    all_food_series_ids = list(series_to_item.keys())

    print(f"Fetching {len(all_food_series_ids)} breakfast item price series "
          f"from FRED ({START_DATE} to present)...")
    raw_prices_df = fetch_fred_series(all_food_series_ids, START_DATE, END_DATE)
    raw_prices_df = clean_and_align(raw_prices_df)

    print("Fetching Headline and Core CPI from FRED...")
    cpi_df = fetch_fred_series(list(CPI_SERIES.values()), START_DATE, END_DATE)
    cpi_df = clean_and_align(cpi_df)

    print("\nCalculating item-level price indices (rebased to 100)...")
    item_index_df = build_item_price_index(raw_prices_df, series_to_item)

    print("Calculating the weighted composite Breakfast Index...")
    composite = build_composite_index(item_index_df, ITEM_WEIGHTS)
    composite_yoy = compute_yoy_pct_change(composite)

    headline_yoy = compute_yoy_pct_change(cpi_df["CPIAUCSL"])
    core_yoy = compute_yoy_pct_change(cpi_df["CPILFESL"])

    print("Writing results to the database...")
    conn = init_database(DB_PATH)
    store_item_prices(conn, raw_prices_df, item_index_df, series_to_item, units)
    store_composite_index(conn, composite, composite_yoy)
    store_cpi_benchmark(conn, cpi_df, headline_yoy, core_yoy)
    conn.close()

    print_summary(composite_yoy, headline_yoy, core_yoy)

    print(f"\nResults saved to: {DB_PATH}")
    print("Open this file in 'DB Browser for SQLite' to inspect the raw "
          "tables, or connect it to Power BI -- see docs/power-bi-setup.md "
          "for click-by-click steps.\n")


if __name__ == "__main__":
    main()
