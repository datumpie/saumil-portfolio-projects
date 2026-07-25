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
