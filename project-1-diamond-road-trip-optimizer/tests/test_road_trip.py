"""
test_road_trip.py
Automated pass/fail validation for the Diamond Road Trip Optimizer.

This test suite does NOT require internet access or a live MLB API call --
it uses a small set of known, hand-verified inputs to confirm the pipeline's
math and logic are correct. This is the "automated pass/fail tests" and
"compare outputs to known-good examples" piece of the Verification Standard
described in docs/validation-checklist.md.

Run with:
    pip install pytest
    pytest tests/test_road_trip.py -v
"""

import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import road_trip  # noqa: E402


# ----------------------------------------------------------------------------
# 1. Distance math: known-good example
#    Wrigley Field (Chicago) to Busch Stadium (St. Louis) is a well-documented
#    ~260-mile straight-line distance. We assert we land in a tight, sane
#    range rather than an exact float, since "known-good" here means
#    "matches public reference distances," not "matches to the inch."
# ----------------------------------------------------------------------------

def test_haversine_known_distance_chicago_to_st_louis():
    wrigley = next(s for s in road_trip.STADIUMS if s[0] == "Wrigley Field")
    busch = next(s for s in road_trip.STADIUMS if s[0] == "Busch Stadium")

    distance = road_trip.haversine_miles(
        wrigley[4], wrigley[5], busch[4], busch[5]
    )

    assert 260 <= distance <= 272, (
        f"Expected ~266 miles between Wrigley Field and Busch Stadium, got {distance}"
    )


def test_haversine_zero_distance_same_point():
    lat, lon = 41.9484, -87.6553
    assert road_trip.haversine_miles(lat, lon, lat, lon) == 0


# ----------------------------------------------------------------------------
# 2. Stadium reference table integrity
# ----------------------------------------------------------------------------

def test_stadium_table_has_no_duplicate_venue_names():
    venue_names = [s[0] for s in road_trip.STADIUMS]
    assert len(venue_names) == len(set(venue_names)), (
        "Duplicate venue_name found in STADIUMS -- this is the primary key "
        "and must be unique."
    )


def test_stadium_table_covers_all_30_franchises():
    team_names = {s[1] for s in road_trip.STADIUMS}
    # 30 franchises, but the Athletics have two rows (two home venues in
    # 2026), so we expect 30 unique team names across 31 rows.
    assert len(team_names) == 30
    assert len(road_trip.STADIUMS) == 31


def test_all_coordinates_are_within_the_continental_us_or_toronto():
    for venue_name, team, city, state, lat, lon in road_trip.STADIUMS:
        assert 20 <= lat <= 55, f"{venue_name} latitude out of range: {lat}"
        assert -130 <= lon <= -65, f"{venue_name} longitude out of range: {lon}"


# ----------------------------------------------------------------------------
# 3. Database schema: confirm tables and columns exist as documented
# ----------------------------------------------------------------------------

def test_database_schema_creates_all_expected_tables(tmp_path):
    db_path = str(tmp_path / "test_road_trip.db")
    conn = road_trip.init_database(db_path)
    road_trip.seed_stadiums(conn)

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert {"stadiums", "games", "trip_legs"}.issubset(tables)

    cur.execute("SELECT COUNT(*) FROM stadiums")
    assert cur.fetchone()[0] == 31

    conn.close()


# ----------------------------------------------------------------------------
# 4. Itinerary builder: fully offline, hand-constructed "known-good" example
#    Three fake games, mimicking exactly the shape fetch_games_for_teams()
#    would produce -- no network call involved.
# ----------------------------------------------------------------------------

def _fake_games():
    return [
        {
            "game_id": 1001,
            "game_date": "2026-08-02",
            "game_datetime": "2026-08-02T18:10:00Z",
            "home_team": "Milwaukee Brewers",
            "away_team": "Pittsburgh Pirates",
            "venue_name": "American Family Field",
            "status": "Scheduled",
        },
        {
            "game_id": 1002,
            "game_date": "2026-08-05",
            "game_datetime": "2026-08-05T18:10:00Z",
            "home_team": "Minnesota Twins",
            "away_team": "Cleveland Guardians",
            "venue_name": "Target Field",
            "status": "Scheduled",
        },
        {
            "game_id": 1003,
            "game_date": "2026-08-10",
            "game_datetime": "2026-08-10T20:15:00Z",
            "home_team": "St. Louis Cardinals",
            "away_team": "Cincinnati Reds",
            "venue_name": "Busch Stadium",
            "status": "Scheduled",
        },
    ]


def test_itinerary_visits_every_team_when_dates_are_generous():
    stadium_lookup = {s[0]: (s[4], s[5]) for s in road_trip.STADIUMS}
    games = _fake_games()

    itinerary, unreachable = road_trip.build_itinerary(
        games=games,
        stadium_lookup=stadium_lookup,
        start_stadium="Wrigley Field",
        start_date_str="08/01/2026",
        avg_speed_mph=55,
        buffer_hours=3,
    )

    visited_teams = {leg["team_visited"] for leg in itinerary}
    assert visited_teams == {"Milwaukee Brewers", "Minnesota Twins", "St. Louis Cardinals"}
    assert unreachable == []

    # Legs must be in strictly increasing chronological order.
    dates = [datetime.strptime(leg["game_date"], "%Y-%m-%d") for leg in itinerary]
    assert dates == sorted(dates)


def test_itinerary_flags_unreachable_team_when_window_too_tight():
    stadium_lookup = {s[0]: (s[4], s[5]) for s in road_trip.STADIUMS}
    games = _fake_games()

    # Start on the same day as the only Cardinals game, from a stadium that
    # is physically too far away to arrive on time -- Cardinals should be
    # reported as unreachable rather than silently dropped or crashing.
    itinerary, unreachable = road_trip.build_itinerary(
        games=[g for g in games if g["home_team"] == "St. Louis Cardinals"],
        stadium_lookup=stadium_lookup,
        start_stadium="Oracle Park",  # San Francisco -- ~1,800 miles away
        start_date_str="08/10/2026",  # same day as the game itself
        avg_speed_mph=55,
        buffer_hours=3,
    )

    assert itinerary == []
    assert unreachable == ["St. Louis Cardinals"]


def test_itinerary_raises_clear_error_for_unknown_start_stadium():
    stadium_lookup = {s[0]: (s[4], s[5]) for s in road_trip.STADIUMS}
    try:
        road_trip.build_itinerary(
            games=_fake_games(),
            stadium_lookup=stadium_lookup,
            start_stadium="Not A Real Stadium",
            start_date_str="08/01/2026",
            avg_speed_mph=55,
            buffer_hours=3,
        )
        assert False, "Expected a ValueError for an unknown start stadium"
    except ValueError as e:
        assert "Not A Real Stadium" in str(e)


# ----------------------------------------------------------------------------
# 5. End-to-end persistence: build an itinerary, write it to SQLite, read
#    it back, and confirm nothing was lost or corrupted in the round trip.
# ----------------------------------------------------------------------------

def test_itinerary_round_trips_through_sqlite(tmp_path):
    db_path = str(tmp_path / "test_road_trip.db")
    conn = road_trip.init_database(db_path)
    road_trip.seed_stadiums(conn)

    games = _fake_games()
    road_trip.store_games(conn, games)
    stadium_lookup = road_trip.load_stadium_lookup(conn)

    itinerary, _ = road_trip.build_itinerary(
        games=games,
        stadium_lookup=stadium_lookup,
        start_stadium="Wrigley Field",
        start_date_str="08/01/2026",
        avg_speed_mph=55,
        buffer_hours=3,
    )
    road_trip.store_itinerary(conn, itinerary)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM trip_legs")
    row_count = cur.fetchone()[0]
    assert row_count == len(itinerary)

    cur.execute("SELECT team_visited FROM trip_legs ORDER BY leg_number")
    stored_teams = [row[0] for row in cur.fetchall()]
    assert stored_teams == [leg["team_visited"] for leg in itinerary]

    conn.close()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
