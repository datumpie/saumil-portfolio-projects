"""
test_stadium_concessions.py
Automated pass/fail validation for the Bark in the Park Concession Optimizer.

This suite checks two different things, on purpose:
  1. The MECHANICS are correct (math, schema, persistence) -- this is
     ordinary software testing.
  2. The SIMULATED DISTRIBUTION is realistic -- since this project's whole
     premise is a statistical proxy for data that can't be obtained
     directly, the tests also assert that season-level aggregates land
     inside real-world MLB attendance and spending ranges (see
     docs/validation-checklist.md for the sourcing behind every bound
     used below).

Run with:
    pip install pytest
    pytest tests/test_stadium_concessions.py -v
"""

import os
import sqlite3
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import stadium_concessions as sc  # noqa: E402


def _simulate(seed=42):
    rng = np.random.default_rng(seed)
    return sc.simulate_season(rng)


# ----------------------------------------------------------------------------
# 1. Schedule generation
# ----------------------------------------------------------------------------

def test_season_has_exactly_81_games():
    games = _simulate()
    assert len(games) == 81


def test_exactly_five_promo_nights():
    games = _simulate()
    promo_count = sum(g["is_promo_night"] for g in games)
    assert promo_count == 5


def test_all_game_dates_fall_within_season_window():
    games = _simulate()
    for g in games:
        game_date = sc.date.fromisoformat(g["game_date"])
        assert sc.SEASON_START <= game_date <= sc.SEASON_END


def test_game_dates_are_unique_and_sorted():
    games = _simulate()
    dates = [g["game_date"] for g in games]
    assert len(dates) == len(set(dates)), "Duplicate game dates found"
    assert dates == sorted(dates), "Game dates are not in chronological order"


# ----------------------------------------------------------------------------
# 2. Reproducibility -- same seed must always produce the same season
# ----------------------------------------------------------------------------

def test_same_seed_produces_identical_season():
    games_a = _simulate(seed=42)
    games_b = _simulate(seed=42)
    assert games_a == games_b


def test_different_seed_produces_a_different_season():
    games_a = _simulate(seed=42)
    games_b = _simulate(seed=99)
    assert games_a != games_b


# ----------------------------------------------------------------------------
# 3. Realism checks -- does the simulated distribution land in a
#    plausible range for actual MLB stadium operations?
#    See docs/validation-checklist.md for the sourcing behind each bound.
# ----------------------------------------------------------------------------

def test_no_game_ever_exceeds_stadium_capacity():
    games = _simulate()
    for g in games:
        assert g["attendance"] <= sc.STADIUM_CAPACITY


def test_no_attendance_is_negative():
    games = _simulate()
    for g in games:
        assert g["attendance"] >= 0


def test_season_average_attendance_is_within_realistic_mlb_range():
    """
    MLB's published 2025 league-average attendance was just over 29,000
    fans/game. This simulation represents a mid-market franchise, so we
    check for a broad, realistic band (20,000-36,000) rather than
    demanding an exact match to the league average.
    """
    games = _simulate()
    avg_attendance = sum(g["attendance"] for g in games) / len(games)
    assert 20000 <= avg_attendance <= 36000, (
        f"Average attendance {avg_attendance:.0f} is outside the "
        f"realistic MLB range"
    )


def test_promo_nights_draw_more_than_standard_nights_on_average():
    games = _simulate()
    promo_avg = np.mean([g["attendance"] for g in games if g["is_promo_night"]])
    standard_avg = np.mean([g["attendance"] for g in games if not g["is_promo_night"]])
    assert promo_avg > standard_avg


def test_revenue_per_cap_is_within_realistic_mlb_range():
    """
    Published fan-spending research (see docs/validation-checklist.md)
    puts total concession spend per attendee roughly in the teens through
    the $40s depending on team and night. Anything under $5 or over $75
    per cap would indicate a broken parameter, not just a low/high night.
    """
    games = _simulate()
    for g in games:
        assert 5.0 <= g["revenue_per_cap"] <= 75.0, (
            f"Game {g['game_id']} revenue_per_cap={g['revenue_per_cap']} "
            f"is outside the realistic range"
        )


def test_specialty_percap_lifts_more_than_standard_percap_on_promo_nights():
    """
    This is the central hypothesis of the model (see the Decision Log in
    README.md): promotion nights shift the REVENUE MIX toward high-margin
    specialty items more than they lift standard-item spending. Confirm
    that's actually true in the simulated output, not just assumed.
    """
    games = _simulate()
    promo_games = [g for g in games if g["is_promo_night"]]
    standard_games = [g for g in games if not g["is_promo_night"]]

    def avg_percap(rows, revenue_key):
        return np.mean([r[revenue_key] / r["attendance"] for r in rows])

    standard_percap_lift = (avg_percap(promo_games, "standard_revenue")
                             - avg_percap(standard_games, "standard_revenue"))
    specialty_percap_lift = (avg_percap(promo_games, "specialty_revenue")
                              - avg_percap(standard_games, "specialty_revenue"))

    assert specialty_percap_lift > standard_percap_lift


def test_promo_nights_are_net_profitable_after_cleaning_cost():
    games = _simulate()
    promo_games = [g for g in games if g["is_promo_night"]]
    assert all(g["net_margin"] > 0 for g in promo_games)


# ----------------------------------------------------------------------------
# 4. Database schema and full persistence round trip
# ----------------------------------------------------------------------------

def test_database_schema_creates_all_expected_tables(tmp_path):
    db_path = str(tmp_path / "test_stadium_concessions.db")
    conn = sc.init_database(db_path)

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert {"games", "revenue_detail"}.issubset(tables)

    conn.close()


def test_full_pipeline_round_trips_through_sqlite(tmp_path):
    db_path = str(tmp_path / "test_stadium_concessions.db")
    games = _simulate()

    conn = sc.init_database(db_path)
    sc.store_games(conn, games)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games")
    assert cur.fetchone()[0] == 81

    # 2 revenue rows (Standard + Specialty) per game
    cur.execute("SELECT COUNT(*) FROM revenue_detail")
    assert cur.fetchone()[0] == 81 * 2

    cur.execute("SELECT COUNT(*) FROM games WHERE is_promo_night = 1")
    assert cur.fetchone()[0] == 5

    # Spot-check that a single game's total_revenue equals the sum of its
    # two revenue_detail rows -- confirms the wide and long tables agree.
    cur.execute("SELECT game_id, total_revenue FROM games LIMIT 1")
    game_id, total_revenue = cur.fetchone()
    cur.execute(
        "SELECT SUM(revenue_amount) FROM revenue_detail WHERE game_id = ?",
        (game_id,),
    )
    detail_sum = cur.fetchone()[0]
    assert round(detail_sum, 2) == round(total_revenue, 2)

    conn.close()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
