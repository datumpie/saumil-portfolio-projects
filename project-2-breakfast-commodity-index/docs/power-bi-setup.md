# Connecting `breakfast_index.db` to Power BI and Building the Dual-Axis Chart

Just like Project 1, Power BI doesn't have a built-in SQLite connector, so
we use the same free ODBC driver approach. If you already set this up for
Project 1, skip to **Part 3** and just add a new DSN for this database.

Total time: about 10-15 minutes (5 minutes if you already have the ODBC
driver installed from Project 1).

---

## Part 1: Install the SQLite ODBC driver (skip if already installed)

1. Go to **http://www.ch-werner.de/sqliteodbc/**
2. Download the **Win64** installer (e.g. `sqliteodbc_w64.exe`).
3. Run it and click **Next** through the defaults, then **Finish**.

---

## Part 2: Point Windows to `breakfast_index.db`

1. Click **Windows Start**, type `ODBC Data Sources`, and open
   **ODBC Data Sources (64-bit)**.
2. Click the **System DSN** tab, then **Add...**
3. Select **SQLite3 ODBC Driver**, click **Finish**.
4. Fill in:
   - **Data Source Name:** `BreakfastIndex`
   - **Database Name:** click **Browse...** and select `breakfast_index.db`
5. Click **OK**.

---

## Part 3: Connect Power BI

1. Open **Power BI Desktop**.
2. **Home > Get Data > More... >** search `ODBC` **> Connect**.
3. Choose DSN **BreakfastIndex > OK**.
4. In the Navigator, check:
   - `item_prices`
   - `composite_index`
   - `cpi_benchmark`
5. Click **Load**.

---

## Part 4: Build the dual-axis line chart

This is the centerpiece visual: the Breakfast Index's inflation rate
against Headline and Core CPI, on **two different vertical axes**.

**Why dual-axis, specifically:** the Breakfast Index swings much harder
than CPI -- a single bad egg-supply year can push it up 20%+ in a year,
while headline CPI rarely moves more than a few percent. If you put all
three lines on one shared axis, the CPI lines flatten out into a nearly
straight line at the bottom of the chart and become useless to read. A
dual-axis chart lets each line use the vertical space it needs while still
showing you whether they move **together** (same direction, same timing)
or **apart**.

1. Click a blank area of the canvas.
2. In Visualizations, click **Line chart**.
3. From `composite_index`, drag **date** into the **X-axis** well.
4. From `composite_index`, drag **breakfast_yoy_pct** into the
   **Y-axis** well (this becomes the primary/left axis).
5. From `cpi_benchmark`, drag **cpi_headline_yoy_pct** into the
   **Secondary Y-axis** well.
6. From `cpi_benchmark`, also drag **cpi_core_yoy_pct** into the
   **Secondary Y-axis** well (both CPI lines will share the right-hand
   axis, which is fine since they move in a similar range).
7. Click the visual, open **Format your visual** (paintbrush icon), and
   under **Y-axis**, rename the primary axis title to "Breakfast Index
   YoY %" and the secondary axis title to "CPI YoY %" so the chart is
   self-explanatory.
8. Optional: under **Format your visual > Lines**, give each series a
   distinct color (e.g., red for Breakfast Index, blue for Headline CPI,
   light blue for Core CPI) so the three lines are easy to tell apart at
   a glance.

You now have one chart showing whether breakfast is currently running
hotter or cooler than the broader economy -- and by how much.

## Part 5: Add the item-level breakdown (optional but useful)

To show *which* item is driving the Breakfast Index:

1. Add a second **Line chart** visual below the first.
2. From `item_prices`, drag **date** into X-axis.
3. Drag **price_index** into Y-axis.
4. Drag **item_name** into **Legend** -- this draws one line per breakfast
   item (all rebased to 100 at the start of the data), so a viewer can see
   at a glance whether, say, eggs or coffee is the real story behind a
   Breakfast Index spike.

---

## Refreshing with new data

Re-run `python breakfast_index.py` any time you want the latest month's
data (see README.md's "Deployment, Maintenance" section for the monthly
cadence). Back in Power BI, click **Home > Refresh** and every visual
updates automatically.
