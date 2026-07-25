# Connecting `stadium_concessions.db` to Power BI and Building the Decomposition Tree

Same free ODBC approach as Projects 1 and 2. If you've already set up the
SQLite ODBC driver, skip to **Part 2**.

Total time: about 10-15 minutes (5 minutes if the driver is already
installed).

---

## Part 1: Install the SQLite ODBC driver (skip if already installed)

1. Go to **http://www.ch-werner.de/sqliteodbc/**
2. Download the **Win64** installer (e.g. `sqliteodbc_w64.exe`).
3. Run it and click **Next** through the defaults, then **Finish**.

---

## Part 2: Point Windows to `stadium_concessions.db`

1. Click **Windows Start**, type `ODBC Data Sources`, and open
   **ODBC Data Sources (64-bit)**.
2. Click the **System DSN** tab, then **Add...**
3. Select **SQLite3 ODBC Driver**, click **Finish**.
4. Fill in:
   - **Data Source Name:** `BarkInThePark`
   - **Database Name:** click **Browse...** and select
     `stadium_concessions.db`
5. Click **OK**.

---

## Part 3: Connect Power BI

1. Open **Power BI Desktop**.
2. **Home > Get Data > More... >** search `ODBC` **> Connect**.
3. Choose DSN **BarkInThePark > OK**.
4. In the Navigator, check both:
   - `games`
   - `revenue_detail`
5. Click **Load**.

---

## Part 4: Build the Decomposition Tree

The Decomposition Tree is a built-in Power BI visual that lets you click
your way down through a total number, one dimension at a time, to see
exactly what's driving it -- perfect for answering "where does the extra
Bark in the Park revenue actually come from?"

1. Click a blank area of the canvas.
2. In the **Visualizations** pane, find and click the **Decomposition
   Tree** icon (it looks like a small branching diagram).
3. From the `revenue_detail` table, drag **revenue_amount** into the
   **Analyze** field well. The visual will show one root node: total
   revenue across every game and category.
4. From `revenue_detail`, drag these three fields into the **Explain By**
   field well (add all three -- you'll choose the order interactively in
   the next step):
   - **is_promo_night**
   - **revenue_category**
   - **day_type**
5. Click the **+** icon that appears next to the root node. A menu pops
   up letting you pick which field to drill into first -- choose
   **is_promo_night**. The tree splits into two branches: promo nights
   and standard nights.
6. Click the **+** next to the "1" (promo) branch, and choose
   **revenue_category**. This splits promo-night revenue into Standard
   vs. Specialty -- this is the exact split that shows the mix-shift
   argument visually.
7. Optional -- try the built-in AI: instead of manually picking a field in
   step 5 or 6, choose **High Value** from that same **+** menu. Power BI
   will automatically pick whichever remaining field produces the
   largest value at that branch, which is a fast way to confirm that
   "Specialty revenue on promo nights" really is the standout driver
   without you having to guess first.

## Part 5: Add supporting visuals next to the tree

For a client-ready dashboard, add two more visuals below or beside the
Decomposition Tree:

**A card showing the ROI verdict:**
1. Add a **Card** visual.
2. Create a new measure (right-click `games` table > **New measure**) with:
   ```
   Net Incremental Profit =
   AVERAGEX(FILTER(games, games[is_promo_night] = 1), games[net_margin])
   - AVERAGEX(FILTER(games, games[is_promo_night] = 0), games[net_margin])
   ```
3. Drag that measure into the Card visual -- this shows, at a glance, the
   dollar figure behind the "does the promotion pay for itself" question.

**A bar chart of revenue per capita by game type:**
1. Add a **Clustered bar chart** visual.
2. Drag **is_promo_night** into the Y-axis (or X-axis) and
   **revenue_per_cap** into Values, with **Average** as the aggregation
   (click the field in the Values well, choose **Average**).

---

## Refreshing with new data

If you re-run `python stadium_concessions.py` (for example, after
changing `ITEM_WEIGHTS`-style parameters at the top of the script), click
**Home > Refresh** in Power BI and every visual, including the
Decomposition Tree, updates automatically.
