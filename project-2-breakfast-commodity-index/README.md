# Project 2: The True Breakfast Commodity Index

**Live FRED economic data + a weighted composite index = a clearer answer
to "is breakfast actually getting more expensive, or is it just eggs?"**

Give it a date range. It pulls live historical retail prices for six
breakfast staples straight from the Federal Reserve's own data system,
builds a single weighted "Breakfast Index," and benchmarks its inflation
rate against Headline and Core CPI -- plus a database you can plug straight
into Power BI for a dual-axis comparison chart.

---

## 1. The Business Problem & Research Requirements

**What problem are we solving?**
Single-commodity price stories make headlines -- "egg prices up 60%!" --
but a single item's price is driven by its *own* supply chain (an avian
flu outbreak, a bad wheat harvest, a coffee-growing region's drought) far
more than by broad economic inflation. Reading too much into one
volatile ingredient gives a distorted picture of what's actually happening
to a household's or a diner's real grocery costs.

**Who benefits?**
A small restaurant or diner owner deciding whether a cost spike is
temporary (ride it out) or part of a genuine, sustained inflation trend
(adjust menu prices); a household budgeting for groceries; a local news
outlet or blogger wanting a defensible, source-backed "true cost of
breakfast" story instead of an anecdotal one.

**Why hasn't this been solved already?**
The government publishes CPI (broad, smoothed, but not breakfast-specific)
and BLS publishes individual item prices (specific, but noisy and
one-dimensional) -- nobody combines a handful of breakfast-relevant items
into one purpose-built index and lines it up against the CPI benchmark in
one place. It's a narrow, practical niche that's easy to build once you
know where the data lives.

**Why hasn't this been solved already? (continued -- the "pancake"
problem)**
If you tried to track "the cost of pancakes" using a single ingredient
like flour or eggs, a single supply shock (say, a poor wheat harvest or an
avian flu outbreak) would swing your index wildly even in a year when
broad inflation barely moved. A diversified basket -- meat, dairy, grain,
an imported commodity (coffee), and produce -- pulls from five genuinely
different supply chains, so no single shock can dominate the whole index.
That's the entire reason this project uses six items and a weighted
average instead of tracking one "hero" ingredient.

**What assumptions are we making?**
- The six chosen items (bacon, eggs, milk, bread, coffee, potatoes)
  reasonably represent "a basic breakfast" -- this is a simplification,
  not an official government basket.
- The item weights in `ITEM_WEIGHTS` are analyst-assigned estimates of
  relative importance in a basic breakfast, not official BLS
  relative-importance weights. See the Decision Log for why, and treat
  the resulting index as directionally meaningful, not as an official
  statistic.
- FRED's republished BLS data is accurate and current as of each pull.
- Rebasing each item's price to 100 at the start of the pulled date range
  is a valid way to make differently-priced, differently-unit-ed items
  comparable (a $6 pack of bacon and a $3 dozen of eggs can't be averaged
  as raw dollars).

**What could cause failure?**
- **A wrong or outdated FRED series ID.** If BLS ever discontinues or
  replaces one of these six series, the pull would fail loudly (a missing
  column, not a silent wrong number) -- see Testing & Validation for the
  exact expected-response check.
- **The weighting scheme not matching the reader's own idea of "a
  breakfast basket."** This is a design choice, not a bug -- and it's why
  `ITEM_WEIGHTS` is a plain, easy-to-edit dictionary at the top of the
  script rather than buried logic.
- **FRED changing or restricting its free CSV-download endpoint.**
  `pandas-datareader` uses this same free method for other sources (e.g.
  Stooq), and that specific source broke in exactly this way in 2026 when
  Stooq began requiring an API key. See Deployment/Maintenance for the
  fallback plan if this ever happens to FRED.

**How do we measure success?**
The tool returns a complete, gap-free monthly time series for all six
items and both CPI benchmarks, a composite index that visibly reacts to
known real-world events (e.g., the 2022-2023 egg price shock), and a
year-over-year inflation comparison that a non-technical reader can
interpret in one glance at the Power BI chart.

**How do we validate results?**
Automated tests check the index math against calculations worked out by
hand (see `docs/validation-checklist.md`), and a manual spot-check
compares a raw pulled price against FRED's own published chart for that
series.

**How do we maintain it?**
Nothing about this project goes stale between runs -- there's no schedule
data to keep in sync (unlike Project 1). The only maintenance is
re-running the script when new monthly data is released (see Deployment
below), and periodically sanity-checking whether the item list or weights
still reflect what "a basic breakfast" should mean.

**How do we extend it?**
Natural next steps: add more items (orange juice, butter, cereal) for a
richer basket; add regional breakdowns (FRED publishes these same series
by Census region); add a seasonally-adjusted variant; publish the monthly
reading automatically as a short blog post on the portfolio site.

**How would we deploy it for a client?**
As a monthly scheduled job: the client (or an automated task) re-runs the
script once BLS releases new CPI and average-price data each month
(typically mid-month for the prior month), and the same `breakfast_index.db`
file feeds a live Power BI report. No servers, no hosting -- the entire
"backend" is a single Python file and a flat database file, identical in
spirit to Project 1.

---

## 2. Architecture & Design Choices

### Data flow

```
FRED (6 food series + 2 CPI series)  --->  pandas-datareader
--->  rebase each item to a 100-based price index  --->  weighted
composite Breakfast Index  --->  SQLite (item_prices, composite_index,
cpi_benchmark)  --->  Power BI (via ODBC)  --->  dual-axis inflation chart
```

### Decision Log

**Choice: pull data via the FRED API (through `pandas-datareader`),
instead of web scraping**
- *Alternatives considered:* Scraping BLS's or FRED's website tables
  directly with a tool like BeautifulSoup; manually copying numbers into
  a spreadsheet each month.
- *Trade-offs:* Web scraping is fragile -- it breaks the moment a site
  redesigns its HTML, and repeatedly scraping a government site raises
  terms-of-service concerns that a documented API avoids entirely. Manual
  copy-paste doesn't scale to a monthly refresh and invites transcription
  errors.
- *Final choice:* The FRED API, accessed through `pandas-datareader`.
- *Business rationale:* FRED is the same U.S. Bureau of Labor Statistics
  data, republished by the Federal Reserve Bank of St. Louis in a stable,
  versioned, citation-ready format -- using it isn't a compromise in
  authority, it's the more convenient path to the exact same numbers.
- *Technical rationale:* `pandas-datareader`'s FRED reader pulls from
  FRED's free public CSV endpoint and needs **no account or API key** for
  this kind of historical series pull -- unlike the official `fredapi`
  package, which requires a free FRED account and key. That matters
  directly for the "copy/paste simple for non-technical users" standard:
  one less signup step.

**Choice: a weighted composite index, instead of a raw average of prices**
- *Alternatives considered:* Simply averaging the six raw dollar prices
  together; averaging the six items' percent changes with equal weight.
- *Trade-offs:* Averaging raw dollar prices is not just imprecise, it's
  mathematically meaningless here -- bacon is priced per pound, eggs per
  dozen, and milk per gallon, so a raw average would just be adding
  unlike units together. Equal-weighting the *percent changes* is closer
  to valid, but it still treats a 1% move in coffee (a smaller, more
  discretionary item) as equally significant as a 1% move in eggs or
  bacon (larger, more central items in a typical breakfast).
- *Final choice:* Rebase each item to its own 100-based price index, then
  combine those six indices into one composite using explicit,
  analyst-assigned expenditure-share weights (`ITEM_WEIGHTS`).
- *Business rationale:* This mirrors how CPI itself is built -- a
  weighted basket, not a flat average -- so the resulting number means
  something comparable to "real" inflation statistics a reader already
  has intuition for.
- *Technical rationale:* Rebasing to 100 makes items with wildly
  different price levels and units directly combinable; explicit weights
  in a plain dictionary (rather than hardcoded math) mean anyone can
  audit or adjust the basket's assumptions in thirty seconds.

**Choice: SQLite, and the same architecture pattern as Project 1**
- *Alternatives considered:* Same as Project 1 -- PostgreSQL, or no
  persistent database at all.
- *Trade-offs:* Identical reasoning to Project 1: no client wants to run
  a database server for a monthly economic-indicator refresh.
- *Final choice:* SQLite, using the exact same "single Python file plus
  flat `.db` file" pattern as Project 1.
- *Business & technical rationale:* Consistency across the portfolio's
  projects means a client who's comfortable with Project 1's setup
  process doesn't have to learn a new one for Project 2 -- the Power BI
  connection steps are nearly copy-paste identical between the two.

---

## 3. Implementation

The complete, working script is `breakfast_index.py` in this folder (also
shown in full below). It requires no other project files to run -- just
Python and the two packages in `requirements.txt`.

```python
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
# Decision Log above for why, and see "What assumptions are we making?"
# for the caveat this creates.
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
    ($/gallon) in a single composite -- see the Decision Log above for why
    raw dollar averaging across mismatched units would be meaningless.

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
    ITEM_WEIGHTS, not just a plain average -- see the Decision Log above
    for why.
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
```

### The FRED Series Reference

| Item | FRED Series ID | Unit |
|---|---|---|
| Bacon | APU0000704111 | $ per lb |
| Eggs | APU0000708111 | $ per dozen |
| Milk | APU0000709112 | $ per gallon |
| Bread | APU0000702111 | $ per lb |
| Coffee | APU0000717311 | $ per lb |
| Potatoes | APU0000712112 | $ per lb |
| Headline CPI | CPIAUCSL | Index (1982-84=100) |
| Core CPI | CPILFESL | Index (1982-84=100) |

### Connecting to Power BI and building the dual-axis chart

Full click-by-click steps -- including installing the free ODBC driver and
building the dual-axis inflation comparison chart -- are in
`docs/power-bi-setup.md`.

---

## 4. Testing & Validation

The full Verification & Reproducibility Standard for this project -- with
a concrete answer for all eight standard questions -- lives in
`docs/validation-checklist.md`. Summary:

- **Automated tests:** `tests/test_breakfast_index.py` contains 9 tests
  that run entirely offline (no live API call needed), covering: the
  item-level price index rebasing math (checked against hand-calculated
  values), the weighted composite index calculation (also hand-checked),
  the weight-validation guard (rejects weights that don't sum to 1.0),
  year-over-year percent change math, missing-data forward-fill handling,
  database schema creation, and full save/reload round-tripping through
  SQLite. Run them with:

  ```
  pip install pytest
  pytest tests/test_breakfast_index.py -v
  ```

  All 9 currently pass.

- **Expected live API behavior:** A working call to
  `pandas_datareader.data.DataReader('CPIAUCSL', 'fred', '2024-01-01', '2024-03-01')`
  should return a small pandas DataFrame with one `CPIAUCSL` column and a
  handful of monthly rows. If it raises a connection or parsing error,
  FRED's public endpoint may be temporarily unreachable, or (less likely)
  the endpoint format has changed -- see "Deployment, Maintenance" below
  for the fallback plan.

- **Manual spot-check:** compare one pulled item price against FRED's own
  published series page, and confirm the 2022-2023 egg price spike shows
  up in the data (see `docs/validation-checklist.md` for the full
  three-step spot-check).

---

## 5. Deployment, Maintenance, and Future Enhancements

### Running it locally

1. Install Python 3.10+ from python.org.
2. Open a terminal in this folder and run `pip install -r requirements.txt`.
3. (Optional) Edit `START_DATE` in the **USER CONFIGURATION** block if you
   want a shorter or longer history.
4. Run `python breakfast_index.py`.
5. Read the printed summary, or connect `breakfast_index.db` to Power BI
   (`docs/power-bi-setup.md`).

### Monthly maintenance

BLS typically releases the prior month's CPI and Average Price data in the
first half of the following month (for example, June's data is usually
released in mid-July). To keep the index current:

1. Re-run `python breakfast_index.py` once a month, any time after the
   new BLS release. Since `END_DATE` is left as `None`, the script always
   pulls through the latest available month automatically -- no date
   editing required.
2. Refresh the Power BI report (**Home > Refresh**).

That's the entire monthly maintenance routine. There is no manual data
entry and nothing to "roll forward" by hand.

### If FRED's free CSV endpoint ever breaks

`pandas-datareader` pulls FRED data through a free, no-signup CSV export
endpoint. This is the same general method that broke for a different
data source (Stooq) in early 2026 when that provider began requiring an
API key. If FRED ever does the same:

1. Sign up for a free FRED API key at
   `https://fredaccount.stlouisfed.org/apikey` (takes about two minutes).
2. Install the official `fredapi` package: `pip install fredapi`.
3. Replace the `fetch_fred_series()` function's body with:
   ```python
   from fredapi import Fred
   fred = Fred(api_key="your_key_here")
   raw = pd.DataFrame({sid: fred.get_series(sid, start_date, end_date)
                        for sid in series_ids})
   ```
   Everything downstream of that function (index math, database writes,
   Power BI connection) stays exactly the same, because it only depends
   on getting a DataFrame with one column per series ID.

### Future enhancements

- **More items** for a richer basket (orange juice, butter, cereal), each
  a one-line addition to `FRED_SERIES` and `ITEM_WEIGHTS`.
- **Regional breakdowns** -- FRED publishes these same average-price
  series broken out by Census region (Northeast, Midwest, South, West),
  which would let the index show whether breakfast inflation is a
  national story or a regional one.
- **Automated monthly publishing** -- have the script post its
  `print_summary()` output as a short update on the portfolio site each
  month, turning this into a running public data feature rather than a
  one-time analysis.
- **A seasonally-adjusted variant**, since some of these items (produce
  especially) have natural seasonal price patterns that a pure YoY
  comparison partially, but not fully, controls for.

---

## Manual Test Checklist (run this before trusting a real index reading)

1. **Run it once with the default configuration** (`START_DATE =
   "2005-01-01"`) exactly as shipped. Confirm it prints a summary with a
   recent month, three inflation percentages, and no Python errors.
2. **Run `pytest tests/test_breakfast_index.py -v`** and confirm all 9
   tests show `PASSED`.
3. **Open `breakfast_index.db`** in Power BI (or any SQLite viewer) and
   confirm `item_prices` has six items per month with `price_index`
   values starting at 100.0 in the first month, and that `composite_index`
   shows a visible jump in `breakfast_yoy_pct` around 2022-2023 (the known
   egg price shock).
