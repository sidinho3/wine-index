# Regional Wine Index

Regional bottle-price indices in the style of Liv-ex (Bordeaux, Burgundy, Champagne, Rhône,
Loire, Piedmont, Tuscany, Rioja, Port & Douro, California, plus country indices), built from the
free Alko price list. Alko is Finland's national wine retailer, and its list has thousands of wines
with country, region, vintage, bottle size and shelf price.

## Weekly routine (about 1 minute)
Alko's site sits behind a bot check, so the price list can't be downloaded automatically. Instead:
1. On alko.fi, download the price list ("Alkon hinnasto", Excel).
2. In this repo on github.com, open the `inbox` folder and choose **Add file → Upload files**,
   drop the .xlsx in, then click **Commit changes**.
3. GitHub Actions saves the snapshot to `data/snapshots/`, rebuilds the indices and republishes the site.

## One-time setup
Go to Settings → Pages → Build and deployment → Source and choose **GitHub Actions**.

## Files
- `wine_index.py`: parses price lists into snapshots (`--inbox` / `--xlsx FILE`) and builds `site/data.js`
- `site/index.html`: the website. You can also open it straight from disk.
- `.github/workflows/weekly.yml`: runs on each upload

## How the index works
- Prices are normalised to a 750ml bottle.
- Each week is chained to the last using only bottles listed in both weeks, so new listings and
  delistings don't move it. The link is the geometric mean of price changes.
- Every index starts at 100 on the first snapshot. "Premium" covers bottles at €30+ per 750ml.
- Alko changes prices in price-list periods (roughly monthly), so expect step-shaped lines.
