"""
road_trip.py
Diamond Road Trip Optimizer
----------------------------------------------------------------------------
Fetches live MLB schedules for a set of target teams within a date window,
matches each game to a real stadium's GPS coordinates, and builds a
distance-optimized road trip itinerary. Results are stored in a local
SQLite database that can be connected directly to Power BI for interactive
mapping.

Project: Datum Pie / Stackend Solutions Portfolio -- Project 1
Author:  Saumil Chokshi
----------------------------------------------------------------------------
HOW TO RUN THIS (non-technical, copy/paste steps):
    1. Install Python 3.10 or newer from https://www.python.org/downloads/
    2. Open a terminal (Command Prompt on Windows, Terminal on Mac) in this
       project folder.
    3. Run:  pip install -r requirements.txt
    4. Edit the USER CONFIGURATION section below (teams, dates, start city).
    5. Run:  python road_trip.py
    6. Read the printed itinerary, or open road_trip.db in Power BI
       (see docs/power-bi-setup.md for click-by-click steps).
----------------------------------------------------------------------------
"""

import sqlite3
import math
import sys
from datetime import datetime, timedelta

try:
    import statsapi
except ImportError:
    print("ERROR: The 'MLB-StatsAPI' package is not installed.")
    print("Run this command first, then try again:")
    print("    pip install -r requirements.txt")
    sys.exit(1)


# ============================================================================
# USER CONFIGURATION -- edit these values, then run the script.
# No other part of this file needs to change for normal use.
# ============================================================================

# Full MLB team names, exactly as MLB writes them (see README.md's
# "Team Name Reference" table for the complete list of all 30).
TEAMS_TO_VISIT = [
    "Chicago Cubs",
    "Milwaukee Brewers",
    "Minnesota Twins",
    "St. Louis Cardinals",
]

# The stadium the road trip starts from. This does NOT have to be one of
# the teams above -- for example, you might start from your home city.
START_STADIUM = "Wrigley Field"

# The road trip window. Format must be MM/DD/YYYY.
START_DATE = "08/01/2026"
END_DATE = "08/20/2026"

# Assumed average driving speed in miles per hour (a realistic highway
# average that already accounts for normal stops). This only affects the
# drive-time estimate shown to you -- it does not affect distances.
AVG_DRIVING_SPEED_MPH = 55

# Minimum hours of buffer between arriving in a city and first pitch, to
# allow for parking, traffic, and picking up tickets.
ARRIVAL_BUFFER_HOURS = 3

# Where the SQLite database file will be created.
DB_PATH = "road_trip.db"


# ============================================================================
# STADIUM REFERENCE TABLE
# GPS coordinates (decimal degrees) for all 30 MLB home ballparks, plus the
# Athletics' 2026 neutral-site venue in Las Vegas (they split home games
# between two parks this season). Verified against public team/venue
# records as of July 2026. See docs/decision-log.md for why this table is
# keyed by VENUE NAME rather than team name.
# ============================================================================

STADIUMS = [
    # (venue_name, team_name, city, state, latitude, longitude)
    ("Oriole Park at Camden Yards", "Baltimore Orioles", "Baltimore", "MD", 39.2839, -76.6217),
    ("Fenway Park", "Boston Red Sox", "Boston", "MA", 42.3467, -71.0972),
    ("Yankee Stadium", "New York Yankees", "Bronx", "NY", 40.8296, -73.9262),
    ("Tropicana Field", "Tampa Bay Rays", "St. Petersburg", "FL", 27.7683, -82.6534),
    ("Rogers Centre", "Toronto Blue Jays", "Toronto", "ON", 43.6414, -79.3894),
    ("Rate Field", "Chicago White Sox", "Chicago", "IL", 41.8299, -87.6338),
    ("Progressive Field", "Cleveland Guardians", "Cleveland", "OH", 41.4962, -81.6852),
    ("Comerica Park", "Detroit Tigers", "Detroit", "MI", 42.3390, -83.0485),
    ("Kauffman Stadium", "Kansas City Royals", "Kansas City", "MO", 39.0517, -94.4803),
    ("Target Field", "Minnesota Twins", "Minneapolis", "MN", 44.9817, -93.2776),
    ("Daikin Park", "Houston Astros", "Houston", "TX", 29.7573, -95.3555),
    ("Angel Stadium", "Los Angeles Angels", "Anaheim", "CA", 33.8003, -117.8827),
    ("Sutter Health Park", "Athletics", "West Sacramento", "CA", 38.5802, -121.5137),
    ("Las Vegas Ballpark", "Athletics", "Summerlin", "NV", 36.1215, -115.3242),
    ("T-Mobile Park", "Seattle Mariners", "Seattle", "WA", 47.5914, -122.3325),
    ("Globe Life Field", "Texas Rangers", "Arlington", "TX", 32.7473, -97.0842),
    ("Truist Park", "Atlanta Braves", "Atlanta", "GA", 33.8907, -84.4677),
    ("loanDepot Park", "Miami Marlins", "Miami", "FL", 25.7781, -80.2196),
    ("Citi Field", "New York Mets", "Queens", "NY", 40.7571, -73.8458),
    ("Citizens Bank Park", "Philadelphia Phillies", "Philadelphia", "PA", 39.9061, -75.1665),
    ("Nationals Park", "Washington Nationals", "Washington", "DC", 38.8730, -77.0074),
    ("Wrigley Field", "Chicago Cubs", "Chicago", "IL", 41.9484, -87.6553),
    ("Great American Ball Park", "Cincinnati Reds", "Cincinnati", "OH", 39.0975, -84.5061),
    ("American Family Field", "Milwaukee Brewers", "Milwaukee", "WI", 43.0280, -87.9712),
    ("PNC Park", "Pittsburgh Pirates", "Pittsburgh", "PA", 40.4469, -80.0057),
    ("Busch Stadium", "St. Louis Cardinals", "St. Louis", "MO", 38.6226, -90.1928),
    ("Chase Field", "Arizona Diamondbacks", "Phoenix", "AZ", 33.4453, -112.0667),
    ("Coors Field", "Colorado Rockies", "Denver", "CO", 39.7559, -104.9942),
    ("Dodger Stadium", "Los Angeles Dodgers", "Los Angeles", "CA", 34.0739, -118.2400),
    ("Petco Park", "San Diego Padres", "San Diego", "CA", 32.7073, -117.1566),
    ("Oracle Park", "San Francisco Giants", "San Francisco", "CA", 37.7786, -122.3893),
]


# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_database(db_path):
    """Create (or reset) the SQLite database and its three tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS stadiums;
        DROP TABLE IF EXISTS games;
        DROP TABLE IF EXISTS trip_legs;

        CREATE TABLE stadiums (
            venue_name   TEXT PRIMARY KEY,
            team_name    TEXT NOT NULL,
            city         TEXT NOT NULL,
            state        TEXT NOT NULL,
            latitude     REAL NOT NULL,
            longitude    REAL NOT NULL
        );

        CREATE TABLE games (
            game_id       INTEGER PRIMARY KEY,
            game_date     TEXT NOT NULL,
            game_datetime TEXT NOT NULL,
            home_team     TEXT NOT NULL,
            away_team     TEXT NOT NULL,
            venue_name    TEXT NOT NULL,
            status        TEXT,
            FOREIGN KEY (venue_name) REFERENCES stadiums(venue_name)
        );

        CREATE TABLE trip_legs (
            leg_number               INTEGER PRIMARY KEY,
            game_id                  INTEGER,
            team_visited             TEXT NOT NULL,
            matchup                  TEXT NOT NULL,
            venue_name                TEXT NOT NULL,
            latitude                 REAL NOT NULL,
            longitude                REAL NOT NULL,
            game_date                TEXT NOT NULL,
            distance_from_prev_miles REAL,
            drive_hours_from_prev    REAL,
            FOREIGN KEY (game_id) REFERENCES games(game_id)
        );
    """)
    conn.commit()
    return conn


def seed_stadiums(conn):
    """Load the STADIUMS reference table into the database."""
    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO stadiums
           (venue_name, team_name, city, state, latitude, longitude)
           VALUES (?, ?, ?, ?, ?, ?)""",
        STADIUMS,
    )
    conn.commit()


def load_stadium_lookup(conn):
    """Return {venue_name: (latitude, longitude)} for fast distance lookups."""
    cur = conn.cursor()
    cur.execute("SELECT venue_name, latitude, longitude FROM stadiums")
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}


# ============================================================================
# LIVE MLB DATA
# ============================================================================

def resolve_team_id(team_name):
    """
    Look up a team's numeric MLB id from its full name using the live API.
    Returns None if no match is found.
    """
    matches = statsapi.lookup_team(team_name, sportIds=1)
    for m in matches:
        if m.get("name") == team_name:
            return m["id"]
    if matches:
        # No exact name match, but at least one candidate came back --
        # use the first one rather than failing outright.
        return matches[0]["id"]
    return None


def parse_game_datetime(game_datetime_str):
    """
    Parse the game_datetime field returned by MLB-StatsAPI. This field is
    a UTC timestamp in ISO 8601 format, e.g. '2026-08-01T18:10:00Z'.
    """
    try:
        return datetime.strptime(game_datetime_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        # Fallback in case MLB returns fractional seconds or a slightly
        # different timestamp format.
        return datetime.fromisoformat(
            game_datetime_str.replace("Z", "+00:00")
        ).replace(tzinfo=None)


def fetch_games_for_teams(teams, start_date, end_date):
    """
    Pull every game for the given list of team names from the live MLB
    Stats API, filtered down to:
      - HOME games only (you can only "visit" a stadium when that team
        is playing at home)
      - Regular season games only (game_type == 'R'), so spring training
        and postseason noise doesn't distort the trip window.
    """
    all_games = []

    for team_name in teams:
        team_id = resolve_team_id(team_name)
        if team_id is None:
            print(f"WARNING: Could not find team '{team_name}' in the MLB "
                  f"Stats API. Check spelling against README.md's team "
                  f"reference table. Skipping this team.")
            continue

        schedule = statsapi.schedule(
            start_date=start_date, end_date=end_date, team=team_id
        )

        for g in schedule:
            if g.get("home_name") != team_name:
                continue  # away game -- can't "visit" this team's park here
            if g.get("game_type") != "R":
                continue  # skip spring training / postseason / exhibitions

            all_games.append({
                "game_id": g["game_id"],
                "game_date": g["game_date"],
                "game_datetime": g["game_datetime"],
                "home_team": g["home_name"],
                "away_team": g["away_name"],
                "venue_name": g["venue_name"],
                "status": g["status"],
            })

    return all_games


def store_games(conn, games):
    cur = conn.cursor()
    for g in games:
        cur.execute(
            """INSERT OR REPLACE INTO games
               (game_id, game_date, game_datetime, home_team, away_team,
                venue_name, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (g["game_id"], g["game_date"], g["game_datetime"], g["home_team"],
             g["away_team"], g["venue_name"], g["status"]),
        )
    conn.commit()


# ============================================================================
# GEOSPATIAL ROUTE OPTIMIZATION
# ============================================================================

def haversine_miles(lat1, lon1, lat2, lon2):
    """
    Great-circle ("as the crow flies") distance between two lat/lon points,
    in miles. This is a straight-line approximation, not a driving-route
    distance -- see docs/decision-log.md for why that trade-off was made
    for v1, and README.md's "What could cause failure" section for the
    practical impact of that assumption.
    """
    earth_radius_miles = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_miles * c


def build_itinerary(games, stadium_lookup, start_stadium, start_date_str,
                     avg_speed_mph, buffer_hours):
    """
    Greedy nearest-neighbor road trip builder.

    Starting from `start_stadium` on `start_date_str`, repeatedly choose the
    geographically closest remaining home game that can still physically be
    reached in time, given the drive time from the current location. This is
    a heuristic, not a true shortest-possible-route solver -- see
    docs/decision-log.md for why that trade-off makes sense at this scale.

    Returns:
        itinerary (list of dicts): the ordered stops
        unreachable_teams (list of str): teams that could not be fit into
            the window at all, given the current settings
    """
    if start_stadium not in stadium_lookup:
        raise ValueError(
            f"Start stadium '{start_stadium}' was not found in the stadium "
            f"reference table. Check spelling against the STADIUMS list."
        )

    current_lat, current_lon = stadium_lookup[start_stadium]
    current_time = datetime.strptime(start_date_str, "%m/%d/%Y")

    # Group games by home team, sorted chronologically, so the earliest
    # feasible game for each team is considered first.
    games_by_team = {}
    for g in games:
        games_by_team.setdefault(g["home_team"], []).append(g)
    for team_games in games_by_team.values():
        team_games.sort(key=lambda g: g["game_datetime"])

    remaining_teams = set(games_by_team.keys())
    itinerary = []
    leg_number = 1

    while remaining_teams:
        best_choice = None
        best_distance = None

        for team in remaining_teams:
            for g in games_by_team[team]:
                venue = g["venue_name"]
                if venue not in stadium_lookup:
                    continue  # no coordinates on file for this venue

                venue_lat, venue_lon = stadium_lookup[venue]
                distance = haversine_miles(current_lat, current_lon, venue_lat, venue_lon)
                drive_hours = distance / avg_speed_mph

                game_dt = parse_game_datetime(g["game_datetime"])
                earliest_possible_arrival = current_time + timedelta(
                    hours=drive_hours + buffer_hours
                )

                if earliest_possible_arrival > game_dt:
                    continue  # physically can't make it in time

                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_choice = {
                        "team": team,
                        "game": g,
                        "distance": distance,
                        "drive_hours": drive_hours,
                        "game_dt": game_dt,
                    }

        if best_choice is None:
            # No remaining team has any reachable game left in the window.
            break

        g = best_choice["game"]
        venue = g["venue_name"]
        venue_lat, venue_lon = stadium_lookup[venue]

        itinerary.append({
            "leg_number": leg_number,
            "game_id": g["game_id"],
            "team_visited": best_choice["team"],
            "matchup": f"{g['away_team']} @ {g['home_team']}",
            "venue_name": venue,
            "latitude": venue_lat,
            "longitude": venue_lon,
            "game_date": g["game_date"],
            "distance_from_prev_miles": round(best_choice["distance"], 1),
            "drive_hours_from_prev": round(best_choice["drive_hours"], 1),
        })

        current_lat, current_lon = venue_lat, venue_lon
        current_time = best_choice["game_dt"]
        remaining_teams.discard(best_choice["team"])
        leg_number += 1

    unreachable_teams = sorted(remaining_teams)
    return itinerary, unreachable_teams


def store_itinerary(conn, itinerary):
    cur = conn.cursor()
    cur.execute("DELETE FROM trip_legs")
    for leg in itinerary:
        cur.execute(
            """INSERT INTO trip_legs
               (leg_number, game_id, team_visited, matchup, venue_name,
                latitude, longitude, game_date, distance_from_prev_miles,
                drive_hours_from_prev)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (leg["leg_number"], leg["game_id"], leg["team_visited"],
             leg["matchup"], leg["venue_name"], leg["latitude"],
             leg["longitude"], leg["game_date"],
             leg["distance_from_prev_miles"], leg["drive_hours_from_prev"]),
        )
    conn.commit()


# ============================================================================
# OUTPUT
# ============================================================================

def print_itinerary(itinerary, unreachable_teams, start_stadium):
    print("\n" + "=" * 60)
    print("DIAMOND ROAD TRIP ITINERARY")
    print("=" * 60)
    print(f"Starting point: {start_stadium}\n")

    if not itinerary:
        print("No feasible itinerary could be built with the current "
              "settings. Try widening the date range.")
        return

    total_miles = 0.0
    for leg in itinerary:
        total_miles += leg["distance_from_prev_miles"]
        print(f"Stop {leg['leg_number']}: {leg['matchup']}")
        print(f"   Venue: {leg['venue_name']}")
        print(f"   Date:  {leg['game_date']}")
        print(f"   Drive from previous stop: {leg['distance_from_prev_miles']} "
              f"miles (~{leg['drive_hours_from_prev']} hours)")
        print()

    print(f"TOTAL ROAD TRIP DISTANCE: {round(total_miles, 1)} miles\n")

    if unreachable_teams:
        print("NOTE: The following teams could NOT be fit into this "
              "itinerary (no home game in the date window could be reached "
              "in time from the rest of the route):")
        for team in unreachable_teams:
            print(f"   - {team}")
        print("\nTry widening the date range, adding more start buffer days, "
              "or adjusting AVG_DRIVING_SPEED_MPH.")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("Diamond Road Trip Optimizer -- starting up...\n")

    conn = init_database(DB_PATH)
    seed_stadiums(conn)

    print(f"Fetching live schedule data for: {', '.join(TEAMS_TO_VISIT)}")
    print(f"Date window: {START_DATE} to {END_DATE}\n")

    games = fetch_games_for_teams(TEAMS_TO_VISIT, START_DATE, END_DATE)

    if not games:
        print("No games were returned for the given teams and date range.")
        print("Double-check team names (see README.md) and dates, then "
              "try again.")
        conn.close()
        return

    store_games(conn, games)
    stadium_lookup = load_stadium_lookup(conn)

    itinerary, unreachable_teams = build_itinerary(
        games=games,
        stadium_lookup=stadium_lookup,
        start_stadium=START_STADIUM,
        start_date_str=START_DATE,
        avg_speed_mph=AVG_DRIVING_SPEED_MPH,
        buffer_hours=ARRIVAL_BUFFER_HOURS,
    )

    store_itinerary(conn, itinerary)
    print_itinerary(itinerary, unreachable_teams, START_STADIUM)

    print(f"Results saved to: {DB_PATH}")
    print("Open this file in 'DB Browser for SQLite' to inspect the raw "
          "tables, or connect it to Power BI -- see docs/power-bi-setup.md "
          "for click-by-click steps.\n")

    conn.close()


if __name__ == "__main__":
    main()
