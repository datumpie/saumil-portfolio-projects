# Project 3: The Bark in the Park Concession Optimizer

**A statistical proxy model for a number no outsider is ever allowed to
see: how much a stadium promotion actually adds to concession revenue,
and whether that's enough to cover what it costs to clean up after it.**

Give it nothing -- it runs out of the box. It simulates a full 81-game
home season with realistic, sourced attendance and spending behavior,
flags five "Bark in the Park" dog-friendly nights the same way a real MLB
team schedules them, and answers one specific question: does the
incremental concession revenue from a themed promotion outweigh the extra
cleaning cost of hosting it?

**A note on the data, up front:** real point-of-sale concession data
belongs to the team and its concessionaire and is never published
anywhere. Everything in `stadium_concessions.db` is **simulated** --
generated from probability distributions whose parameters are grounded in
public industry benchmarks (cited throughout this document), not pulled
from any real team's books. This is a proxy model for demonstrating an
analytical method, not a claim about any specific franchise's actual
finances.

---

## 1. The Business Problem & Research Requirements

**What problem are we solving?**
A team's ops and marketing departments need to know whether a themed
promotion like Bark in the Park is worth running again -- but the
concession revenue data that would answer that question sits inside a
concessionaire's proprietary point-of-sale system, not in anything the
team's own analysts can query directly. Without a way to model the
expected revenue behavior, "should we run more theme nights" becomes a
gut call instead of a data-backed one.

**Who benefits?**
A team's business operations or fan-experience department deciding
whether to expand a promotional calendar; a concessions/hospitality
partner deciding how to staff and stock a themed night differently from a
standard one; a finance team weighing the added operational cost
(sanitation, insurance, extra staff) of a novelty promotion against its
revenue upside.

**Why hasn't this been solved already?**
The data that would solve it directly -- actual per-transaction POS
records -- is locked inside a vendor's proprietary system and essentially
never shared externally, even internally across departments in some
cases. A statistical proxy model, built from publicly available industry
benchmarks and clearly labeled as an estimate, is the practical way to
get a defensible answer without that data.

**What assumptions are we making?**
- Attendance and per-cap spending are modeled as random variables drawn
  from Normal distributions, parameterized from public benchmarks (see
  the Decision Log and `docs/validation-checklist.md`'s Parameter
  Sourcing table for the specific sources behind every number).
- The promotion attendance lift (+35% average) and the cleaning-cost
  add-on ($2,500/promo night) are **analyst-assigned estimates**, clearly
  disclosed as such -- not sourced external statistics, because
  team-specific promo-lift and vendor-specific cleaning-cost data is
  exactly the kind of proprietary number this project works around.
- The stadium represents a generic mid-market MLB franchise (38,000
  capacity) -- this is not modeling any specific real team.
- Five Bark in the Park nights per season is realistic: the Detroit
  Tigers' actual 2026 promotional calendar lists exactly five Bark in the
  Park dates, which is the direct real-world precedent for this project's
  `NUM_PROMO_NIGHTS = 5`.

**What could cause failure?**
- **Parameter drift from reality.** If a client's actual per-cap spending
  or promo lift is meaningfully different from the ranges used here, the
  dollar figures won't transfer directly -- but the *method* (separate
  standard vs. specialty tracking, compare incremental revenue to
  incremental cost) still applies once real parameters are substituted.
  See Deployment below for exactly how to do that substitution.
- **Treating simulated output as real financial data.** This risk is
  addressed head-on by labeling every deliverable (this README, the
  script's own docstring, the database's contents) as a simulation.
- **Ignoring day-of-week confounding.** Real teams deliberately schedule
  promotions on lower-demand weeknights, which means a naive
  promo-vs-non-promo comparison partly reflects "which night of the week"
  rather than "the promotion itself." This model handles it by
  preferentially scheduling promo nights on weekdays (matching real
  practice) and by keeping `day_type` as a separate field throughout, so
  Query 4 in `analysis.sql` can isolate the day-of-week effect from the
  promotion effect.

**How do we measure success?**
The simulation produces attendance and per-cap figures that stay inside
realistic MLB ranges (validated automatically -- see Testing &
Validation), and the resulting revenue mix shows a larger lift in the
specialty/high-margin category than in the standard category on promo
nights, which is the specific mechanism the business case rests on.

**How do we validate results?**
Every distribution parameter is checked against a cited public benchmark,
and an automated test suite re-verifies the resulting simulated
distribution lands in a realistic range on every run (see
`docs/validation-checklist.md`).

**How do we maintain it?**
This is a self-contained simulation with no external data dependency, so
there's nothing to keep "in sync." Maintenance means periodically
revisiting the assumption values (attendance means, per-cap means, the
promo lift, the cleaning cost) as real benchmarks are updated, and -- most
importantly -- swapping in real client data once it becomes available
(see Deployment below).

**How do we extend it?**
Add more theme-night types (fireworks nights, bobblehead giveaways) each
with their own revenue-mix signature; model weather as an attendance
factor; add a ticket-revenue module alongside the concessions module for
a fuller promotion ROI picture; extend the cleaning-cost model to vary by
actual attendance rather than a flat add-on.

**How would we deploy it for a client?**
This is where the proxy model earns its keep: a real team already has
its own actual POS export (typically a per-transaction or per-game CSV
from the concessionaire) and its own actual attendance figures. The
entire point of building this model on clean, separated tables
(`games`, `revenue_detail`) with an explicit standard/specialty split is
that a client can replace the *simulated* numbers with their *real* ones
using the exact same schema -- every downstream SQL query, every Power BI
visual, and the ROI logic itself, all keep working unchanged. See
Deployment below for the specific swap-in steps.

### The Cleaning Cost Offset -- the core business argument

A dog-friendly promotion is not a free attendance boost. It brings real,
disclosed operational costs on top of a normal game night: extra
sanitation crew, pet-waste stations, and a more thorough post-event
clean of the concourse (`CLEANING_COST_PROMO_ADDON` in the script). A
skeptical ops manager's instinct is reasonable: *"this promotion creates
extra cleanup work -- is it actually worth it?"*

The answer this model gives is decisively yes, and the reason why is the
entire point of separating standard from specialty revenue in the first
place. Bark in the Park attendees aren't just more numerous -- they spend
differently. They're there for an experience, not just a baseball game,
and that experience-seeking behavior shows up specifically in the
high-margin specialty category (in this simulation, specialty items grow
from roughly 17% of the revenue mix on a standard night to roughly 35-40%
on a promo night). That mix shift, multiplied across an attendance bump,
produces incremental revenue that dwarfs the added cleaning cost by a
wide margin -- see the exact figures in `analysis.sql`'s Query 3 output,
reproduced in Testing & Validation below.

---

## 2. Architecture & Design Choices

### Data flow

```
NumPy random distributions (attendance, standard spend, specialty spend)
  --->  81-game season simulation, with 5 games flagged as promo nights
  --->  SQLite (games: wide/one-row-per-game, revenue_detail: long/tidy)
  --->  analysis.sql (Revenue Per Capita by game type)
  --->  Power BI (via ODBC)  --->  Decomposition Tree + supporting visuals
```

### Decision Log

**Choice: model fan behavior using NumPy probability distributions,
instead of fixed point estimates**
- *Alternatives considered:* A single deterministic average per-cap
  figure applied to every game (no randomness at all); bootstrapping from
  real scraped data (not available -- this is exactly the proprietary-data
  problem this project exists to work around).
- *Trade-offs:* A fixed point estimate is simpler to build, but it's
  unrealistic and analytically useless -- it can't answer "how much does
  this vary game-to-game," "how confident are we in the average," or "how
  often does a promo night actually underperform." Real fan purchasing
  behavior is the aggregate of thousands of independent, small decisions,
  which is precisely the situation a Normal distribution is a reasonable
  model for (Central Limit Theorem reasoning), rather than reaching for a
  more complex distribution family that this project's scale doesn't
  justify.
- *Final choice:* `numpy.random.default_rng()` with a fixed seed,
  drawing from Normal distributions for both attendance and per-cap
  spending, clipped to physically sensible bounds (attendance can't
  exceed stadium capacity or go negative).
- *Business rationale:* A distribution-based model produces a *range* of
  plausible outcomes, which is what a promotion-planning conversation
  actually needs -- not a single number presented as certain.
- *Technical rationale:* NumPy's modern `Generator` API
  (`default_rng(seed)`) gives fully reproducible results from a fixed
  seed while still being genuinely randomized behavior -- essential for
  the Verification Standard's "restore from backup" and "compare to
  known-good examples" requirements.

**Choice: separate standard concession revenue from specialty/high-margin
revenue, instead of one blended per-cap number**
- *Alternatives considered:* A single "concession revenue" figure per
  game with no category breakdown.
- *Trade-offs:* A blended number can tell you *that* promo nights make
  more money, but not *why* -- and "why" is the only version of this
  finding a client can act on. If a client can't tell whether the extra
  revenue came from more hot dogs or more premium items, they can't make
  an informed decision about inventory, staffing, or pricing for the next
  theme night.
- *Final choice:* Two explicitly separate revenue streams
  (`standard_revenue`, `specialty_revenue`) simulated with different
  parameters and different promo-night responses, plus a long-format
  `revenue_detail` table specifically so this split is a first-class
  dimension in the Power BI Decomposition Tree, not just a SQL detail.
- *Business rationale:* This split is what turns "promotions make more
  money" into "promotions make more money because of a specific,
  actionable behavioral shift toward premium items" -- the second version
  is what a concessions operations team can actually use.
- *Technical rationale:* Keeping both a wide table (`games`, one row per
  game -- ideal for the per-game SQL math in `analysis.sql`) and a long
  table (`revenue_detail`, one row per game per category -- ideal for
  Power BI's Decomposition Tree) means each consumer of the data gets the
  shape it actually needs, without forcing SQL or Power BI to reshape
  data that the other one needs in a different form.

**Choice: SQLite, and the same architecture pattern as Projects 1 and 2**
- *Alternatives considered:* Same as the prior two projects --
  PostgreSQL, or no persistent database.
- *Trade-offs:* Identical reasoning to Projects 1 and 2 -- no client
  wants to stand up a database server for a promotional-calendar
  analysis tool.
- *Final choice:* SQLite, using the same "single Python file plus flat
  `.db` file" pattern as the rest of the portfolio.
- *Business & technical rationale:* Consistency across the portfolio
  means the Power BI connection steps in `docs/power-bi-setup.md` are
  nearly copy-paste identical to Projects 1 and 2 -- a client or reader
  who's set this up once doesn't have to relearn it.

---

## 3. Implementation

Two files do all the work: `stadium_concessions.py` generates the
season and writes it to SQLite, and `analysis.sql` runs the actual
business-question queries against that database. Both are shown in full
below.

### `stadium_concessions.py`

```python
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
```

### `analysis.sql`

```sql
-- ============================================================================
-- analysis.sql
-- The Bark in the Park Concession Optimizer -- SQL Analysis
-- ----------------------------------------------------------------------------
-- Run this against stadium_concessions.db (created by stadium_concessions.py)
-- to answer the core business question: does a Bark in the Park promotion
-- pay for itself, and where specifically does the extra revenue come from?
--
-- HOW TO RUN THIS (non-technical, copy/paste steps):
--   Option A -- DB Browser for SQLite (free, no command line):
--     1. Download DB Browser for SQLite: https://sqlitebrowser.org/dl/
--     2. Open stadium_concessions.db in it.
--     3. Click the "Execute SQL" tab, paste this whole file in, click Run.
--   Option B -- command line (if you have Python/sqlite3 installed):
--     sqlite3 stadium_concessions.db < analysis.sql
-- ============================================================================


-- ----------------------------------------------------------------------------
-- QUERY 1: Revenue Per Capita by game type
-- The headline number: how does average per-fan spending compare between a
-- Bark in the Park night and a standard game?
-- ----------------------------------------------------------------------------
SELECT
    CASE WHEN is_promo_night = 1 THEN 'Bark in the Park (Promo)'
         ELSE 'Standard Game' END                  AS game_type,
    COUNT(*)                                        AS games,
    ROUND(AVG(attendance), 0)                       AS avg_attendance,
    ROUND(AVG(revenue_per_cap), 2)                  AS avg_revenue_per_cap,
    ROUND(AVG(total_revenue), 2)                    AS avg_total_revenue
FROM games
GROUP BY is_promo_night
ORDER BY is_promo_night DESC;


-- ----------------------------------------------------------------------------
-- QUERY 2: The revenue MIX shift -- standard vs. specialty per-cap spending
-- This is the mechanism behind Query 1's result: does the extra per-cap
-- revenue on promo nights come from fans buying more hot dogs, or from fans
-- buying more of the high-margin specialty items? (See README.md's Decision
-- Log for why this split matters.)
-- ----------------------------------------------------------------------------
SELECT
    CASE WHEN is_promo_night = 1 THEN 'Bark in the Park (Promo)'
         ELSE 'Standard Game' END                          AS game_type,
    ROUND(AVG(standard_revenue / attendance), 2)            AS avg_standard_percap,
    ROUND(AVG(specialty_revenue / attendance), 2)           AS avg_specialty_percap,
    ROUND(
        AVG(specialty_revenue / attendance)
        / (AVG(standard_revenue / attendance) + AVG(specialty_revenue / attendance)) * 100,
        1
    )                                                        AS specialty_share_pct
FROM games
GROUP BY is_promo_night
ORDER BY is_promo_night DESC;


-- ----------------------------------------------------------------------------
-- QUERY 3: The ROI question -- does the incremental revenue from a promo
-- night cover the incremental cleaning cost?
-- This is the single most important query in the project: it directly
-- answers the "operational cleaning cost offset" business question.
-- ----------------------------------------------------------------------------
WITH standard_avg AS (
    SELECT
        AVG(total_revenue) AS avg_revenue,
        AVG(cleaning_cost) AS avg_cost
    FROM games
    WHERE is_promo_night = 0
),
promo_avg AS (
    SELECT
        AVG(total_revenue) AS avg_revenue,
        AVG(cleaning_cost) AS avg_cost
    FROM games
    WHERE is_promo_night = 1
)
SELECT
    ROUND(promo_avg.avg_revenue - standard_avg.avg_revenue, 2)  AS incremental_revenue,
    ROUND(promo_avg.avg_cost - standard_avg.avg_cost, 2)        AS incremental_cleaning_cost,
    ROUND(
        (promo_avg.avg_revenue - standard_avg.avg_revenue)
        - (promo_avg.avg_cost - standard_avg.avg_cost),
        2
    )                                                            AS net_incremental_profit,
    CASE
        WHEN (promo_avg.avg_revenue - standard_avg.avg_revenue)
             > (promo_avg.avg_cost - standard_avg.avg_cost)
        THEN 'YES -- incremental revenue covers the incremental cleaning cost'
        ELSE 'NO -- incremental revenue does NOT cover the incremental cleaning cost'
    END                                                          AS verdict
FROM standard_avg, promo_avg;


-- ----------------------------------------------------------------------------
-- QUERY 4: Revenue Per Capita by day of week
-- Context query: confirms the well-known weekday/weekend attendance pattern
-- shows up in spending too, and helps separate "this was just a Friday
-- night" from "this was a promotion" when reading results.
-- ----------------------------------------------------------------------------
SELECT
    day_of_week,
    day_type,
    COUNT(*)                          AS games,
    ROUND(AVG(attendance), 0)         AS avg_attendance,
    ROUND(AVG(revenue_per_cap), 2)    AS avg_revenue_per_cap
FROM games
GROUP BY day_of_week, day_type
ORDER BY
    CASE day_of_week
        WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
    END;


-- ----------------------------------------------------------------------------
-- QUERY 5: Every Bark in the Park night, ranked by net margin
-- A game-by-game leaderboard -- useful for spotting whether one particular
-- promo date underperformed (bad weather, weak opponent) rather than the
-- promotion concept itself.
-- ----------------------------------------------------------------------------
SELECT
    game_date,
    day_of_week,
    attendance,
    revenue_per_cap,
    total_revenue,
    cleaning_cost,
    net_margin
FROM games
WHERE is_promo_night = 1
ORDER BY net_margin DESC;
```

### Connecting to Power BI and building the Decomposition Tree

Full click-by-click steps are in `docs/power-bi-setup.md`.

---

## 4. Testing & Validation

The full Verification & Reproducibility Standard for this project -- with
a concrete answer for all eight standard questions, plus the specific
real-world benchmark behind every simulated parameter -- lives in
`docs/validation-checklist.md`. Summary:

- **Automated tests:** `tests/test_stadium_concessions.py` contains 15
  tests covering schedule generation (exactly 81 games, exactly 5 promo
  nights, unique chronological dates), reproducibility (same seed always
  produces the same season), and -- most importantly for a simulation --
  **realism bounds**: attendance never exceeds capacity, season-average
  attendance falls between 20,000-36,000, every game's revenue per cap
  falls between $5-$75, and the model's central thesis (specialty per-cap
  lift exceeds standard per-cap lift on promo nights) actually holds in
  the generated data. Run with:

  ```
  pip install pytest
  pytest tests/test_stadium_concessions.py -v
  ```

  All 15 currently pass.

- **The actual output, for reference** (from a real run of this exact
  script with `RANDOM_SEED = 42`):

  | | Standard nights (n=76) | Bark in the Park nights (n=5) |
  |---|---|---|
  | Avg attendance | 27,398 | 32,068 |
  | Avg revenue per cap | $22.84 | $31.32 |
  | Specialty share of revenue | 16.7% | 37.6% |
  | Net incremental profit vs. a standard night | -- | **+$382,571.72** |

- **Manual spot-check:** confirm the 5 promo dates are spread across
  different months and mostly land on weekdays (matching the real
  Detroit Tigers 2026 precedent cited in the Business Problem section),
  and confirm the specialty revenue share is meaningfully higher on promo
  nights using `analysis.sql`'s Query 2 (see `docs/validation-checklist.md`
  for the full three-step spot-check).

---

## 5. Deployment and Future Enhancements

### Running it locally

1. Install Python 3.10+ from python.org.
2. Open a terminal in this folder and run `pip install -r requirements.txt`.
3. Run `python stadium_concessions.py`.
4. Run `analysis.sql` (see the "how to run" note at the top of that file)
   for the full SQL breakdown, or connect `stadium_concessions.db` to
   Power BI (`docs/power-bi-setup.md`).

### Deploying this for a real team client, using their actual POS data

This is the deployment path that matters most for this particular
project. A real client already has the two things this model simulates:

1. **Actual attendance figures**, from their ticketing system, by game
   and date.
2. **Actual concession revenue**, from their concessionaire's POS export
   -- typically broken out by item or item category already, since most
   modern POS systems categorize SKUs.

To swap simulated data for real data:

1. Skip `simulate_season()` entirely. Instead, load the client's
   attendance and POS exports (commonly CSV or Excel) using `pandas` --
   the `xlsx`/`csv` reading pattern is the same as Project 2's FRED data
   loading.
2. Map the client's item-level POS categories into the two buckets this
   model already uses: **Standard** (staple items: hot dogs, basic
   drinks, popcorn) and **Specialty** (premium/novelty/experience items).
   Most POS systems already tag items with a category or department code
   that makes this a lookup, not a manual re-classification.
3. Compute `standard_revenue`, `specialty_revenue`, `total_revenue`, and
   `revenue_per_cap` directly from the real numbers (no distribution
   needed -- this is now actual data, not a simulation).
4. Get the real cleaning/sanitation cost delta for a promo night from the
   client's own operations or vendor invoices, replacing
   `CLEANING_COST_PROMO_ADDON`.
5. Feed the result into `init_database()`, `store_games()`, and
   `analysis.sql` completely unchanged -- this is exactly why the schema
   was designed as clean, generic columns (`attendance`,
   `standard_revenue`, `specialty_revenue`, `cleaning_cost`) rather than
   anything simulation-specific. The Power BI Decomposition Tree and
   every other visual keep working without modification.

### Future enhancements

- **A ticket-revenue module** alongside the concessions module, for a
  complete promotion ROI picture (concessions is only one piece of a
  theme night's economics).
- **Weather as an attendance factor** -- rain and extreme heat are known,
  significant attendance drivers that this model currently doesn't
  capture.
- **A confidence-interval view in Power BI**, showing not just the
  average incremental profit but the range of outcomes across simulated
  seasons, using the model's built-in randomness to run many trials
  instead of just one.
- **Additional theme-night types** (fireworks, bobbleheads, jersey
  nights) each with their own revenue-mix signature, so a client can
  compare which type of promotion produces the best specialty-item lift.

---

## Manual Test Checklist (run this before trusting a real ROI reading)

1. **Run `python stadium_concessions.py`** exactly as shipped. Confirm it
   prints a summary with exactly 76 standard nights, exactly 5 Bark in
   the Park nights, and a "Verdict: YES" line, with no Python errors.
2. **Run `pytest tests/test_stadium_concessions.py -v`** and confirm all
   15 tests show `PASSED`.
3. **Run `analysis.sql`'s Query 2** (the revenue mix query) and confirm
   the specialty item's share of revenue is meaningfully higher on
   Bark in the Park nights than on standard nights -- this is the model's
   central claim, and it should be visibly true in the numbers, not just
   asserted in this document.
