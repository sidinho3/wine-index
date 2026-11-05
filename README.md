# Regional Wine Index

Liv-ex-style regional bottle-price indices (Bordeaux, Burgundy, Champagne, Rhône, Loire,
Piedmont, Tuscany, Rioja, Port & Douro, California, plus country indices), built from the
free Alko price list. Alko is Finland's national wine retailer, and its list has thousands of wines
with country, region, vintage, bottle size and shelf price.

## Files
- `wine_index.py`: downloads the price list, saves a weekly snapshot to `data/snapshots/`, and rebuilds `site/data.js`
- `site/index.html`: the website. Open it straight from disk; no server is needed.
- `run_weekly.bat`: what Windows Task Scheduler runs each week

## Setup on Windows
1. Install Python 3 from python.org and tick "Add to PATH".
2. `pip install openpyxl`
3. First pull: `python wine_index.py`, then open `site\index.html`.
4. Weekly schedule (Mondays 08:00):
   `schtasks /Create /TN "Wine Index weekly" /SC WEEKLY /D MON /ST 08:00 /TR "\"%CD%\run_weekly.bat\""`

## How the index works
- Prices are normalised to a 750ml bottle.
- Each week is chained to the last using only bottles listed in both weeks, so new listings and
  delistings don't move it. The link is the geometric mean of price changes.
- Every index starts at 100 on the first snapshot. "Premium" covers bottles at €30+ per 750ml.
- Alko changes prices in price-list periods (roughly monthly), so expect step-shaped lines.
- History starts from the first pull. There is no backfill.

## Later
- Swap in a paid feed (Wine-Searcher or Liv-ex) by replacing `download()` / `parse_alko()`.
- Publish: push this folder to GitHub and serve `site/` with GitHub Pages plus a weekly Action.
