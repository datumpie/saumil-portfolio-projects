"""
stadium_concessions.py
The Bark in the Park Concession Optimizer -- Statistical Promotion Proxy Model
----------------------------------------------------------------------------
Real point-of-sale concession data is proprietary to each team and its
concessionaire -- it is never published. This script builds a STATISTICAL
PROXY of an 81-game MLB home season instead: realistic attendance and
concession-spending behavior, generated from probability distributions
whose parameters are grounded in publicly available industry benchmarks
(league attendance averages, published fan-spending surveys, and real
team promotional calendars). Five games are flagged as "Bark in the Park"
theme nights, matching the real-world pattern of MLB dog-friendly
promotions (see README.md for the sourcing behind every assumption).

This is SIMULATED data for demonstrating an analytical method -- it is
not, and is not presented as, any real team's actual financial results.

Project: Datum Pie / Stackend Solutions Portfolio -- Project 3
Author:  Saumil Chokshi
----------------------------------------------------------------------------
HOW TO RUN THIS (non-technical, copy/paste steps):
    1. Install Python 3.10 or newer from https://www.python.org/downloads/
    2. Open a terminal (Command Prompt on Windows, Terminal on Mac) in this
       project folder.
    3. Run:  pip install -r requirements.txt
    4. (Optional) Edit the USER CONFIGURATION section below.
    5. Run:  python stadium_concessions.py
    6. Read the printed summary, run analysis.sql for deeper SQL queries,
       or open stadium_concessions.db in Power BI (see
       docs/power-bi-setup.md for click-by-click Decomposition Tree steps).
----------------------------------------------------------------------------
"""

import sqlite3
import sys
from datetime import date, timedelta

try:
    import numpy as np
except ImportError:
    print("ERROR: The 'numpy' package is not installed.")
    print("Run this command first, then try again:")
    print("    pip install -r requirements.txt")
    sys.exit(1)


# ============================================================================
# USER CONFIGURATION -- edit these values, then run the script.
# No other part of this file needs to change for normal use.
# ============================================================================

RANDOM_SEED = 42          # fixed seed = same "season" every run (reproducible)
SEASON_YEAR = 2026
HOME_GAMES = 81            # every MLB team plays exactly 81 home games
NUM_PROMO_NIGHTS = 5       # matches a real 2026 MLB team's Bark in the Park slate
STADIUM_CAPACITY = 38000   # a round, representative mid-market MLB capacity
DB_PATH = "stadium_concessions.db"

# Season window used to spread 81 home games realistically across a schedule
# (early April through late September, the standard MLB regular-season span).
SEASON_START = date(SEASON_YEAR, 4, 2)
SEASON_END = date(SEASON_YEAR, 9, 27)

# ============================================================================
# ATTENDANCE MODEL PARAMETERS
# Weekday/weekend split is the single biggest driver of raw attendance in
# real MLB gate data. Means are set so the season-long blended average
# lands close to MLB's published 2025 league-average attendance of ~29,000
# fans/game. See docs/validation-checklist.md for the exact check.
# ============================================================================

ATTENDANCE_PARAMS = {
    "weekday": {"mean": 24000, "std": 3500},   # Mon-Thu
    "weekend": {"mean": 32500, "std": 4000},   # Fri-Sun
}

# Promotions are modeled as a multiplicative lift on whatever the day's
# baseline attendance would otherwise have been -- this is a disclosed
# analyst assumption (not a cited external statistic; real per-team lift
# data is exactly the kind of proprietary number this project works
# around). See the Decision Log in README.md.
PROMO_ATTENDANCE_LIFT_MEAN = 1.35   # +35% average lift
PROMO_ATTENDANCE_LIFT_STD = 0.08

# ============================================================================
# CONCESSION SPENDING MODEL PARAMETERS
# Two separate categories, deliberately kept separate -- see the Decision
# Log in README.md for why blending them hides the actual mechanism that
# makes a theme night profitable.
# ============================================================================

# STANDARD items: hot dogs, basic drinks, popcorn -- driven by baseline
# hunger/thirst, not by the theme of the night. Only a small weekend bump.
STANDARD_PERCAP_PARAMS = {
    "weekday": {"mean": 18.50, "std": 3.00},
    "weekend": {"mean": 19.50, "std": 3.00},
}

# SPECIALTY items: higher-margin, novelty/experience items (on a Bark in
# the Park night, this includes the themed specialty bakery treat stand).
# Baseline uptake is low on an ordinary night; promo nights see a large
# jump because theme-night attendees are there for the EXPERIENCE, not
# just the baseball, and pay a premium for something novel.
SPECIALTY_PERCAP_BASELINE = {"mean": 4.00, "std": 1.50}
SPECIALTY_PERCAP_PROMO = {"mean": 11.00, "std": 3.00}

# ============================================================================
# OPERATIONAL COST MODEL PARAMETERS
# A disclosed, editable assumption representing the added sanitation load
# of a dog-friendly night (extra concourse crew, pet-waste stations,
# post-event deep clean). This is the "hidden cost" side of the ROI
# question this project answers -- see README.md's Business Problem
# section for the full argument.
# ============================================================================

CLEANING_COST_BASELINE = 1800     # every game has some baseline cleaning cost
CLEANING_COST_PROMO_ADDON = 2500  # extra cost specifically for a promo night


# ============================================================================
# SCHEDULE GENERATION
# ============================================================================

def generate_season_dates(start, end, num_games, rng):
    """
    Spread `num_games` home dates evenly across the season window, then
    jitter slightly so the schedule doesn't look artificially uniform
    (real homestands cluster; this keeps the day-of-week mix realistic
    without needing to model actual travel/opponent schedules, which
    would be over-engineering for this project's purpose).
    """
    total_days = (end - start).days
    # Evenly spaced base offsets across the season...
    base_offsets = np.linspace(0, total_days, num_games)
    # ...with a small random jitter so dates aren't perfectly mechanical.
    jitter = rng.integers(low=-1, high=2, size=num_games)  # -1, 0, or +1 day
    offsets = np.clip(base_offsets + jitter, 0, total_days)
    offsets = np.sort(offsets).astype(int)

    # The base spacing between games is only ~2.2 days, so jittering can
    # occasionally push two offsets into collision. Force strictly
    # increasing, unique offsets by nudging any collision forward one day
    # at a time -- this keeps every game date unique without discarding
    # the jitter's realism.
    for i in range(1, len(offsets)):
        if offsets[i] <= offsets[i - 1]:
            offsets[i] = offsets[i - 1] + 1
    if offsets[-1] > total_days:
        # Extremely unlikely with 81 games across ~180 days, but shift
        # the whole run back into range if a chain of nudges overflowed.
        overflow = offsets[-1] - total_days
        offsets = offsets - overflow

    dates = [start + timedelta(days=int(o)) for o in offsets]
    return dates


def classify_day(game_date):
    """Friday/Saturday/Sunday count as 'weekend' games for this model."""
    # Python's date.weekday(): Monday=0 ... Sunday=6
    return "weekend" if game_date.weekday() in (4, 5, 6) else "weekday"


def choose_promo_nights(game_dates, num_promo_nights, rng):
    """
    Pick which games are Bark in the Park nights. Real MLB teams deliberately
    schedule theme nights on lower-demand weekdays to lift an otherwise-soft
    draw (see README.md's Business Problem section) -- so this model
    preferentially selects from weekday games, falling back to any game if
    there aren't enough weekday dates available.
    """
    weekday_indices = [i for i, d in enumerate(game_dates)
                        if classify_day(d) == "weekday"]

    if len(weekday_indices) >= num_promo_nights:
        chosen = rng.choice(weekday_indices, size=num_promo_nights, replace=False)
    else:
        chosen = rng.choice(len(game_dates), size=num_promo_nights, replace=False)

    return set(int(i) for i in chosen)


# ============================================================================
# GAME SIMULATION
# ============================================================================

def simulate_season(rng):
    """
    Build the full 81-game synthetic season: one dict per game with
    attendance, revenue, and cost fields.
    """
    game_dates = generate_season_dates(SEASON_START, SEASON_END, HOME_GAMES, rng)
    promo_indices = choose_promo_nights(game_dates, NUM_PROMO_NIGHTS, rng)

    games = []
    for i, game_date in enumerate(game_dates):
        day_type = classify_day(game_date)
        is_promo = i in promo_indices

        # --- Attendance ---
        att_params = ATTENDANCE_PARAMS[day_type]
        base_attendance = rng.normal(att_params["mean"], att_params["std"])

        if is_promo:
            lift = rng.normal(PROMO_ATTENDANCE_LIFT_MEAN, PROMO_ATTENDANCE_LIFT_STD)
            base_attendance *= max(lift, 1.0)  # a promo never lowers attendance

        attendance = int(np.clip(base_attendance, 0, STADIUM_CAPACITY))

        # --- Standard concession spending (hot dogs, drinks, popcorn) ---
        std_params = STANDARD_PERCAP_PARAMS[day_type]
        standard_percap = max(rng.normal(std_params["mean"], std_params["std"]), 0)
        standard_revenue = attendance * standard_percap

        # --- Specialty concession spending (premium/novelty items) ---
        if is_promo:
            spec_params = SPECIALTY_PERCAP_PROMO
        else:
            spec_params = SPECIALTY_PERCAP_BASELINE
        specialty_percap = max(rng.normal(spec_params["mean"], spec_params["std"]), 0)
        specialty_revenue = attendance * specialty_percap

        # Round each component FIRST, then derive every downstream figure
        # from those rounded values -- this guarantees standard_revenue +
        # specialty_revenue == total_revenue to the penny, with no
        # independent-rounding drift between the two.
        standard_revenue = round(standard_revenue, 2)
        specialty_revenue = round(specialty_revenue, 2)
        total_revenue = round(standard_revenue + specialty_revenue, 2)
        revenue_per_cap = round(total_revenue / attendance, 2) if attendance > 0 else 0.0

        # --- Operational cleaning cost ---
        cleaning_cost = CLEANING_COST_BASELINE + (CLEANING_COST_PROMO_ADDON if is_promo else 0)
        net_margin = round(total_revenue - cleaning_cost, 2)

        games.append({
            "game_id": i + 1,
            "game_date": game_date.isoformat(),
            "day_of_week": game_date.strftime("%A"),
            "day_type": day_type,
            "is_promo_night": 1 if is_promo else 0,
            "attendance": attendance,
            "standard_revenue": standard_revenue,
            "specialty_revenue": specialty_revenue,
            "total_revenue": total_revenue,
            "revenue_per_cap": revenue_per_cap,
            "cleaning_cost": cleaning_cost,
            "net_margin": net_margin,
        })

    return games


# ============================================================================
# DATABASE SETUP AND PERSISTENCE
# ============================================================================

def init_database(db_path):
    """Create (or reset) the SQLite database and its two tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS games;
        DROP TABLE IF EXISTS revenue_detail;

        CREATE TABLE games (
            game_id           INTEGER PRIMARY KEY,
            game_date         TEXT NOT NULL,
            day_of_week       TEXT NOT NULL,
            day_type          TEXT NOT NULL,
            is_promo_night    INTEGER NOT NULL,
            attendance        INTEGER NOT NULL,
            standard_revenue  REAL NOT NULL,
            specialty_revenue REAL NOT NULL,
            total_revenue     REAL NOT NULL,
            revenue_per_cap   REAL NOT NULL,
            cleaning_cost     REAL NOT NULL,
            net_margin        REAL NOT NULL
        );

        -- Long ("tidy") format of the same revenue data, one row per
        -- game per revenue category. This is what makes the Power BI
        -- Decomposition Tree able to drill Total Revenue -> Promo/Standard
        -- -> Revenue Category in one clean visual -- see
        -- docs/power-bi-setup.md.
        CREATE TABLE revenue_detail (
            detail_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id           INTEGER NOT NULL,
            game_date         TEXT NOT NULL,
            day_type          TEXT NOT NULL,
            is_promo_night    INTEGER NOT NULL,
            revenue_category  TEXT NOT NULL,
            revenue_amount    REAL NOT NULL,
            FOREIGN KEY (game_id) REFERENCES games(game_id)
        );
    """)
    conn.commit()
    return conn


def store_games(conn, games):
    cur = conn.cursor()
    for g in games:
        cur.execute(
            """INSERT INTO games
               (game_id, game_date, day_of_week, day_type, is_promo_night,
                attendance, standard_revenue, specialty_revenue, total_revenue,
                revenue_per_cap, cleaning_cost, net_margin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (g["game_id"], g["game_date"], g["day_of_week"], g["day_type"],
             g["is_promo_night"], g["attendance"], g["standard_revenue"],
             g["specialty_revenue"], g["total_revenue"], g["revenue_per_cap"],
             g["cleaning_cost"], g["net_margin"]),
        )

        for category, amount in (("Standard", g["standard_revenue"]),
                                  ("Specialty", g["specialty_revenue"])):
            cur.execute(
                """INSERT INTO revenue_detail
                   (game_id, game_date, day_type, is_promo_night,
                    revenue_category, revenue_amount)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (g["game_id"], g["game_date"], g["day_type"],
                 g["is_promo_night"], category, amount),
            )
    conn.commit()


# ============================================================================
# OUTPUT
# ============================================================================

def print_summary(games):
    promo_games = [g for g in games if g["is_promo_night"] == 1]
    standard_games = [g for g in games if g["is_promo_night"] == 0]

    def avg(rows, key):
        return sum(r[key] for r in rows) / len(rows) if rows else 0.0

    print("\n" + "=" * 60)
    print("THE BARK IN THE PARK CONCESSION OPTIMIZER")
    print("=" * 60)
    print(f"\nSeason: {SEASON_YEAR}  |  {HOME_GAMES} home games  |  "
          f"{len(promo_games)} Bark in the Park nights\n")

    print("Standard game nights (n={}):".format(len(standard_games)))
    print(f"   Avg attendance:        {avg(standard_games, 'attendance'):,.0f}")
    print(f"   Avg revenue per cap:   ${avg(standard_games, 'revenue_per_cap'):.2f}")
    print(f"   Avg total revenue:     ${avg(standard_games, 'total_revenue'):,.2f}")
    print(f"   Avg cleaning cost:     ${avg(standard_games, 'cleaning_cost'):,.2f}")
    print(f"   Avg net margin:        ${avg(standard_games, 'net_margin'):,.2f}\n")

    print("Bark in the Park nights (n={}):".format(len(promo_games)))
    print(f"   Avg attendance:        {avg(promo_games, 'attendance'):,.0f}")
    print(f"   Avg revenue per cap:   ${avg(promo_games, 'revenue_per_cap'):.2f}")
    print(f"   Avg total revenue:     ${avg(promo_games, 'total_revenue'):,.2f}")
    print(f"   Avg cleaning cost:     ${avg(promo_games, 'cleaning_cost'):,.2f}")
    print(f"   Avg net margin:        ${avg(promo_games, 'net_margin'):,.2f}\n")

    incremental_revenue = avg(promo_games, 'total_revenue') - avg(standard_games, 'total_revenue')
    incremental_cost = avg(promo_games, 'cleaning_cost') - avg(standard_games, 'cleaning_cost')
    incremental_profit = incremental_revenue - incremental_cost

    print("The ROI question -- does the extra concession revenue cover the")
    print("extra cleaning cost of a dog-friendly night?")
    print(f"   Incremental revenue vs. a standard night:  +${incremental_revenue:,.2f}")
    print(f"   Incremental cleaning cost:                 +${incremental_cost:,.2f}")
    print(f"   Net incremental profit:                     ${incremental_profit:,.2f}")
    verdict = "YES" if incremental_profit > 0 else "NO"
    print(f"   Verdict: {verdict}, the incremental concession revenue "
          f"{'more than covers' if incremental_profit > 0 else 'does not cover'} "
          f"the added cleaning cost.")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("Simulating the Bark in the Park concession season...\n")
    rng = np.random.default_rng(RANDOM_SEED)

    games = simulate_season(rng)

    conn = init_database(DB_PATH)
    store_games(conn, games)
    conn.close()

    print_summary(games)

    print(f"\nResults saved to: {DB_PATH}")
    print("Run analysis.sql against this database for the full SQL")
    print("breakdown, or connect it to Power BI -- see")
    print("docs/power-bi-setup.md for click-by-click Decomposition Tree steps.\n")


if __name__ == "__main__":
    main()
