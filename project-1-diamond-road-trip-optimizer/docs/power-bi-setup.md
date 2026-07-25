# Connecting `road_trip.db` to Power BI

Power BI does not have a built-in ("native") connector for SQLite files.
Instead, we use a small free translator program called an **ODBC driver**,
which lets Power BI talk to any SQLite file on your computer. This is a
one-time setup -- once it's done, you'll never have to repeat these steps
again, even for future trips.

Total time: about 10-15 minutes.

---

## Part 1: Install the SQLite ODBC driver (one-time setup)

1. Go to **http://www.ch-werner.de/sqliteodbc/** in your web browser.
2. Find the **Win64** section and download the file named something like
   `sqliteodbc_w64.exe` (make sure it says **64-bit** -- Power BI Desktop
   is almost always 64-bit).
3. Double-click the downloaded file to run it.
4. Click **Next**, accept the license, and click **Next** through the
   remaining screens using the default options. Click **Finish**.

---

## Part 2: Point Windows to your database file (one-time setup)

1. Click the **Windows Start** button and type: `ODBC Data Sources`
2. Open the app called **ODBC Data Sources (64-bit)**.
3. Click the **System DSN** tab.
4. Click **Add...**
5. In the list of drivers, find and select **SQLite3 ODBC Driver**, then
   click **Finish**.
6. A configuration window opens. Fill in:
   - **Data Source Name:** `DiamondRoadTrip` (you can type exactly this)
   - **Database Name:** click **Browse...** and select your
     `road_trip.db` file (the one `road_trip.py` created)
7. Click **OK** to save. You should now see `DiamondRoadTrip` listed under
   the System DSN tab.

> **If you re-run `road_trip.py` later** (for a new trip or a new season),
> you do **not** need to redo this setup -- the DSN always points at the
> same file path, and the file gets overwritten with fresh data each run.

---

## Part 3: Connect Power BI to the database

1. Open **Power BI Desktop**.
2. On the **Home** tab, click **Get Data > More...**
3. In the search box, type `ODBC` and select **ODBC**, then click
   **Connect**.
4. From the **Data source name (DSN)** dropdown, choose
   **DiamondRoadTrip**, then click **OK**.
5. In the **Navigator** window that appears, check the boxes next to:
   - `stadiums`
   - `games`
   - `trip_legs`
6. Click **Load**.

Power BI will import all three tables. You'll see them listed on the right
side of the screen under **Data**.

---

## Part 4: Build the interactive map

1. Click on a blank area of the report canvas.
2. In the **Visualizations** pane, click the **Map** icon (a globe with a
   location pin).
3. With the empty map visual selected, drag fields from the `trip_legs`
   table onto it:
   - Drag **latitude** into the **Latitude** well.
   - Drag **longitude** into the **Longitude** well.
   - Drag **matchup** into the **Legend** well (this labels each stop by
     the game being played there).
   - Drag **leg_number** into the **Tooltips** well (so hovering over a
     dot shows its order in the trip).
4. Resize the map to fill most of the page.
5. Click on the map once, then, in the Visualizations pane, open the
   **Format your visual** (paintbrush) tab and turn on **Data labels** if
   you want each stop labeled directly on the map.

At this point you have an interactive map with one dot per stop on your
road trip, correctly plotted by GPS coordinates, sized by nothing in
particular (feel free to drag `distance_from_prev_miles` into the
**Size** well if you want bigger dots for longer legs).

### Optional: draw the actual route line between stops

The built-in Map visual plots points but does not draw a connecting line
between them in sequence. If you want to see the literal driving path:

1. Go to **Insert > Get more visuals** in Power BI Desktop.
2. Search for **"Icon Map"** (a free custom visual from Microsoft
   AppSource) and click **Add**.
3. Follow the same field setup as above (latitude, longitude, and use its
   built-in **route/line** option, sorting by `leg_number`).

This is optional polish -- the standard Map visual with tooltips already
satisfies the "interactive map" requirement on its own.

---

## Part 5: Add a table of the full itinerary

For a client-ready view, add a **Table** visual next to the map:

1. Click the **Table** icon in Visualizations.
2. Drag in, from `trip_legs`: `leg_number`, `matchup`, `venue_name`,
   `game_date`, `distance_from_prev_miles`, `drive_hours_from_prev`.
3. Click the column header of `leg_number` to sort the table in trip
   order.

You now have a two-panel dashboard: an interactive map on one side, and
the full leg-by-leg itinerary as a sortable table on the other -- ready to
screen-share with a client or drop into the portfolio site as a screenshot
or embedded report.

---

## Refreshing with new data

Whenever you re-run `road_trip.py` with new teams or dates, the same
`road_trip.db` file is overwritten with fresh results. Back in Power BI,
just click **Home > Refresh** and the map and table will update
automatically -- no need to redo the ODBC/DSN setup.
