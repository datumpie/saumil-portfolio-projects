# Verification & Reproducibility Standard -- Project 2: The True Breakfast Commodity Index

A third party should be able to answer **YES** to all eight questions below.
Here is exactly how, for this project.

| # | Question | How it's satisfied here |
|---|----------|--------------------------|
| 1 | Can they recreate this from documentation alone? | Yes. `README.md`'s "Deployment" section gives copy/paste setup steps requiring only Python and one `pip install` command -- no FRED account or API key needed for the default method. |
| 2 | Can they verify the APIs? | Yes. Run `python -c "import pandas_datareader.data as web; print(web.DataReader('CPIAUCSL', 'fred', '2024-01-01', '2024-03-01'))"` -- if this prints a small table of numbers instead of an error, the live FRED connection is working. |
| 3 | Can they confirm the DB tables? | Yes. Open `breakfast_index.db` in any SQLite browser and confirm the three tables `item_prices`, `composite_index`, and `cpi_benchmark` exist, matching the schema in `breakfast_index.py`'s `init_database()` function. |
| 4 | Can they run automated pass/fail tests? | Yes. `pytest tests/test_breakfast_index.py -v` runs 9 tests covering index-rebasing math, the weighted composite calculation, year-over-year change math, missing-data handling, database schema, and full round-trip persistence -- all offline, no live API call required. |
| 5 | Can they compare outputs to known-good examples? | Yes. `test_item_price_index_matches_hand_calculated_values` and `test_composite_index_matches_hand_calculated_weighted_average` check the index math against numbers worked out by hand in the test file's own comments -- anyone can re-verify with a calculator. |
| 6 | Can they restore from backup? | Yes. `breakfast_index.db` is a single flat file, and every table is fully rebuilt from FRED on each run. "Restore" is simply re-running `python breakfast_index.py`. |
| 7 | Can they update dependencies safely? | Yes. Three dependencies, all version-pinned in `requirements.txt`. Run `pytest tests/test_breakfast_index.py` after any upgrade -- if all 9 tests still pass, the upgrade is safe. |
| 8 | Can they explain the business value? | Yes. See `README.md` section 1, "Business Problem & Research Requirements" -- explains in plain language why a single-commodity price (like eggs alone) is a misleading inflation signal, and how this index fixes that. |

## Manual Spot-Check (in addition to automated tests)

Automated tests catch logic errors, but they can't catch a wrong FRED
series ID or a stale weighting assumption. Before trusting the index for
a real decision:

1. Pick one item (e.g., Eggs) and one recent month. Look up
   `APU0000708111` directly on fred.stlouisfed.org and confirm the raw
   price in `item_prices` matches what FRED shows for that month.
2. Sanity-check the shape, not just the number: eggs should show a sharp
   spike around 2022-2023 (avian flu outbreak) in both this tool's data
   and on FRED's own chart for `APU0000708111`. If that spike is missing
   from your pulled data, something is wrong with the date range or the
   series ID.
3. Compare the Breakfast Index's overall trend direction against Headline
   CPI's trend direction over the full history. They won't move in
   lockstep, but multi-year trend direction (both rising through
   2021-2023, both cooling into 2024-2025) should broadly agree -- if the
   Breakfast Index is trending sharply in the opposite direction of CPI
   for a long stretch with no news event to explain it, double-check the
   weights and the underlying series IDs before reporting the finding.
