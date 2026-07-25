"""
test_breakfast_index.py
Automated pass/fail validation for the True Breakfast Commodity Index.

This test suite does NOT require internet access or a live FRED API call.
It builds a small, hand-verifiable synthetic dataset (a few months of made-up
but realistic prices) and checks the math against calculations done by hand.
This is the "automated pass/fail tests" and "compare outputs to known-good
examples" piece of the Verification Standard described in
docs/validation-checklist.md.

Run with:
    pip install pytest
    pytest tests/test_breakfast_index.py -v
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import breakfast_index as bi  # noqa: E402


# ----------------------------------------------------------------------------
# Helper: a small, hand-verifiable synthetic price dataset.
# Two items, three months, chosen so the index math can be checked by hand.
# ----------------------------------------------------------------------------

def _synthetic_raw_prices():
    dates = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
    df = pd.DataFrame(
        {
            "APU_TEST_A": [2.00, 2.20, 2.40],   # +10%, then +9.09%
            "APU_TEST_B": [4.00, 4.00, 3.60],   # flat, then -10%
        },
        index=dates,
    )
    df.index.name = "date"
    return df


_SERIES_TO_ITEM = {"APU_TEST_A": "Item A", "APU_TEST_B": "Item B"}
_TEST_WEIGHTS = {"Item A": 0.6, "Item B": 0.4}


# ----------------------------------------------------------------------------
# 1. Item-level price index: known-good hand calculation
# ----------------------------------------------------------------------------

def test_item_price_index_rebases_to_100_at_first_month():
    raw = _synthetic_raw_prices()
    index_df = bi.build_item_price_index(raw, _SERIES_TO_ITEM)

    assert index_df["Item A"].iloc[0] == 100.0
    assert index_df["Item B"].iloc[0] == 100.0


def test_item_price_index_matches_hand_calculated_values():
    raw = _synthetic_raw_prices()
    index_df = bi.build_item_price_index(raw, _SERIES_TO_ITEM)

    # Item A: 2.00 -> 2.20 -> 2.40, base = 2.00
    # Month 2 index = 2.20 / 2.00 * 100 = 110.0
    # Month 3 index = 2.40 / 2.00 * 100 = 120.0
    assert round(index_df["Item A"].iloc[1], 4) == 110.0
    assert round(index_df["Item A"].iloc[2], 4) == 120.0

    # Item B: 4.00 -> 4.00 -> 3.60, base = 4.00
    # Month 2 index = 100.0 (flat)
    # Month 3 index = 3.60 / 4.00 * 100 = 90.0
    assert round(index_df["Item B"].iloc[1], 4) == 100.0
    assert round(index_df["Item B"].iloc[2], 4) == 90.0


# ----------------------------------------------------------------------------
# 2. Composite index: known-good hand calculation of the weighted average
# ----------------------------------------------------------------------------

def test_composite_index_matches_hand_calculated_weighted_average():
    raw = _synthetic_raw_prices()
    index_df = bi.build_item_price_index(raw, _SERIES_TO_ITEM)
    composite = bi.build_composite_index(index_df, _TEST_WEIGHTS)

    # Month 1: 100*0.6 + 100*0.4 = 100.0
    assert round(composite.iloc[0], 4) == 100.0

    # Month 2: (110.0 * 0.6) + (100.0 * 0.4) = 66.0 + 40.0 = 106.0
    assert round(composite.iloc[1], 4) == 106.0

    # Month 3: (120.0 * 0.6) + (90.0 * 0.4) = 72.0 + 36.0 = 108.0
    assert round(composite.iloc[2], 4) == 108.0


def test_composite_index_rejects_weights_that_dont_sum_to_one():
    raw = _synthetic_raw_prices()
    index_df = bi.build_item_price_index(raw, _SERIES_TO_ITEM)
    bad_weights = {"Item A": 0.5, "Item B": 0.6}  # sums to 1.1

    try:
        bi.build_composite_index(index_df, bad_weights)
        assert False, "Expected a ValueError for weights that don't sum to 1.0"
    except ValueError as e:
        assert "must sum to 1.0" in str(e)


def test_real_item_weights_sum_to_one():
    """Guards the actual ITEM_WEIGHTS shipped in the script, not just a test fixture."""
    assert abs(sum(bi.ITEM_WEIGHTS.values()) - 1.0) < 0.001


# ----------------------------------------------------------------------------
# 3. Year-over-year percent change
# ----------------------------------------------------------------------------

def test_yoy_pct_change_known_value():
    dates = pd.date_range("2023-01-01", periods=13, freq="MS")
    # Flat at 100 for 12 months, then jumps to 110 in month 13.
    values = [100.0] * 12 + [110.0]
    series = pd.Series(values, index=dates)

    yoy = bi.compute_yoy_pct_change(series)

    # First 12 entries have no prior-year comparison -> NaN.
    assert yoy.iloc[:12].isna().all()
    # 13th month: (110 - 100) / 100 * 100 = 10.0%
    assert round(yoy.iloc[12], 4) == 10.0


# ----------------------------------------------------------------------------
# 4. Missing-data handling
# ----------------------------------------------------------------------------

def test_clean_and_align_forward_fills_gaps(capsys):
    dates = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
    df = pd.DataFrame({"APU_TEST_A": [2.00, None, 2.40]}, index=dates)

    cleaned = bi.clean_and_align(df)

    assert cleaned["APU_TEST_A"].iloc[1] == 2.00  # forward-filled from Jan
    assert cleaned.isna().sum().sum() == 0

    captured = capsys.readouterr()
    assert "missing month" in captured.out


# ----------------------------------------------------------------------------
# 5. Database schema and full persistence round trip
# ----------------------------------------------------------------------------

def test_database_schema_creates_all_expected_tables(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "test_breakfast_index.db")
    conn = bi.init_database(db_path)

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert {"item_prices", "composite_index", "cpi_benchmark"}.issubset(tables)

    conn.close()


def test_full_pipeline_round_trips_through_sqlite(tmp_path):
    """
    End-to-end test using the synthetic dataset: build indices, persist to
    SQLite, then read every table back and confirm nothing was lost or
    corrupted in the round trip.
    """
    db_path = str(tmp_path / "test_breakfast_index.db")

    raw = _synthetic_raw_prices()
    index_df = bi.build_item_price_index(raw, _SERIES_TO_ITEM)
    composite = bi.build_composite_index(index_df, _TEST_WEIGHTS)
    composite_yoy = bi.compute_yoy_pct_change(composite)

    # Reuse the same synthetic frame to stand in for CPI data in this test.
    cpi_df = raw.rename(columns={"APU_TEST_A": "CPIAUCSL", "APU_TEST_B": "CPILFESL"})
    headline_yoy = bi.compute_yoy_pct_change(cpi_df["CPIAUCSL"])
    core_yoy = bi.compute_yoy_pct_change(cpi_df["CPILFESL"])

    conn = bi.init_database(db_path)
    units = {"Item A": "$ per test-unit", "Item B": "$ per test-unit"}
    bi.store_item_prices(conn, raw, index_df, _SERIES_TO_ITEM, units)
    bi.store_composite_index(conn, composite, composite_yoy)
    bi.store_cpi_benchmark(conn, cpi_df, headline_yoy, core_yoy)

    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM item_prices")
    assert cur.fetchone()[0] == 6  # 2 items x 3 months

    cur.execute("SELECT COUNT(*) FROM composite_index")
    assert cur.fetchone()[0] == 3

    cur.execute(
        "SELECT price_index FROM item_prices WHERE item_name='Item A' AND date='2024-02-01'"
    )
    assert round(cur.fetchone()[0], 4) == 110.0

    conn.close()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
