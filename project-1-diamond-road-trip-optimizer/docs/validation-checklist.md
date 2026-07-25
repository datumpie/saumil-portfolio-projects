# Verification & Reproducibility Standard -- Project 1: Diamond Road Trip Optimizer

A third party should be able to answer **YES** to all eight questions below.
Here is exactly how, for this project.

| # | Question | How it's satisfied here |
|---|----------|--------------------------|
| 1 | Can they recreate this from documentation alone? | Yes. `README.md` "Deployment" section gives copy/paste setup steps requiring only Python and one `pip install` command. No undocumented manual steps. |
| 2 | Can they verify the APIs? | Yes. Run `python -c "import statsapi; print(statsapi.schedule(date='07/10/2026'))"` -- if this prints a list of games instead of an error, the live MLB Stats API connection is working. |
| 3 | Can they confirm the DB tables? | Yes. Open `road_trip.db` in any SQLite browser (e.g., "DB Browser for SQLite", free) and confirm the three tables `stadiums` (31 rows), `games`, and `trip_legs` exist, matching the schema in `road_trip.py`'s `init_database()` function. |
| 4 | Can they run automated pass/fail tests? | Yes. `pytest tests/test_road_trip.py -v` runs 10 tests covering distance math, stadium data integrity, database schema, itinerary logic, and full round-trip persistence -- all offline, no live API call required. |
| 5 | Can they compare outputs to known-good examples? | Yes. `test_haversine_known_distance_chicago_to_st_louis` checks the Wrigley Field -> Busch Stadium distance against the publicly documented ~266-mile straight-line distance between Chicago and St. Louis. |
| 6 | Can they restore from backup? | Yes. `road_trip.db` is a single flat file. "Backup" is a file copy; "restore" is replacing the file and re-running `python road_trip.py`, which fully rebuilds all three tables from scratch every time it runs. There is no accumulating state to lose. |
| 7 | Can they update dependencies safely? | Yes. Only two dependencies exist (`MLB-StatsAPI`, `pytest`), both pinned with minimum/exact versions in `requirements.txt`. Run `pytest tests/test_road_trip.py` after any dependency upgrade -- if all 10 tests still pass, the upgrade is safe. |
| 8 | Can they explain the business value? | Yes. See `README.md` section 1, "Business Problem & Research Requirements" -- one paragraph, no jargon, answering what problem this solves and who benefits. |

## Manual Spot-Check (in addition to automated tests)

Automated tests catch logic errors, but they can't catch a mislabeled
stadium or a stale API field. Before trusting a real itinerary:

1. Pick one stop in your generated itinerary and look up that same game on
   MLB.com's schedule page. Confirm the date, matchup, and venue match.
2. Right-click the venue's coordinates from `stadiums` (in Google Maps,
   paste `latitude,longitude`) and confirm the pin lands on the actual
   ballpark, not a nearby city block.
3. Add up the `distance_from_prev_miles` column by hand for a 2-3 stop
   trip and compare the total to what Google Maps' driving directions
   shows for the same stops. Expect the tool's number to run **5-15%
   lower** than Google's driving distance -- this is normal and expected;
   see "What Could Cause Failure" in `README.md` for why.
