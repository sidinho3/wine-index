#!/usr/bin/env python3
"""Weekly regional wine bottle-price indices built from Alko's public price list.

Alko (Finland's state retailer) publishes its full catalogue as a free Excel file,
with country, region, vintage, bottle size and shelf price for every wine.

Each run:
  1. downloads the current price list (or uses --xlsx FILE),
  2. saves this week's wine rows to data/snapshots/YYYY-MM-DD.csv,
  3. rebuilds site/data.js from every snapshot, which site/index.html reads.

Index method (similar in spirit to published fine-wine indices):
  * prices are normalised to a 750ml bottle;
  * each week is linked to the previous one using only bottles listed in both
    weeks (same product number and size), so new listings and delistings do not
    move the index;
  * the link is the geometric mean of the price relatives (a chained Jevons
    index), and every index starts at 100 on the first snapshot.

Usage:
  python wine_index.py              # download, snapshot, rebuild
  python wine_index.py --xlsx FILE  # use a file you downloaded yourself
  python wine_index.py --build-only # just rebuild site/data.js
"""
import argparse
import csv
import datetime as dt
import io
import json
import math
import pathlib
import re
import statistics
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
SNAP_DIR = ROOT / "data" / "snapshots"
OUT_JS = ROOT / "site" / "data.js"

ALKO_URL = ("https://www.alko.fi/INTERSHOP/static/WFS/Alko-OnlineShop-Site/-/Alko-OnlineShop/"
            "fi_FI/Alkon%20Hinnasto%20Tekstitiedostona/alkon-hinnasto-tekstitiedostona.xlsx")

MIN_MATCHED = 5          # fewer matched bottles than this -> treat the week as unchanged
PREMIUM_EUR = 30.0       # "premium" tier: 750ml price at or above this in the earlier week

# Finnish country names used by Alko -> English
COUNTRIES = {
    "ranska": "France", "italia": "Italy", "espanja": "Spain", "portugali": "Portugal",
    "saksa": "Germany", "itävalta": "Austria", "yhdysvallat": "USA", "chile": "Chile",
    "argentiina": "Argentina", "australia": "Australia", "uusi-seelanti": "New Zealand",
    "etelä-afrikka": "South Africa", "unkari": "Hungary", "kreikka": "Greece",
    "georgia": "Georgia", "libanon": "Lebanon", "israel": "Israel", "slovenia": "Slovenia",
    "kroatia": "Croatia", "romania": "Romania", "bulgaria": "Bulgaria", "moldova": "Moldova",
    "sveitsi": "Switzerland", "englanti": "England", "iso-britannia": "United Kingdom",
    "kanada": "Canada", "uruguay": "Uruguay", "brasilia": "Brazil", "kiina": "China",
    "japani": "Japan", "suomi": "Finland", "tšekki": "Czechia", "slovakia": "Slovakia",
    "luxemburg": "Luxembourg", "kypros": "Cyprus", "turkki": "Turkey", "armenia": "Armenia",
    "pohjois-makedonia": "North Macedonia", "serbia": "Serbia", "montenegro": "Montenegro",
}

# Regional indices: (id, display name, country in English, region keywords; empty = whole country)
REGIONS = [
    ("bordeaux",   "Bordeaux",   "France",   ["bordeaux"]),
    ("burgundy",   "Burgundy",   "France",   ["bourgogne", "burgund", "chablis", "beaujolais"]),
    ("champagne",  "Champagne",  "France",   ["champagne"]),
    ("rhone",      "Rhône",      "France",   ["rhône", "rhone"]),
    ("loire",      "Loire",      "France",   ["loire"]),
    ("piedmont",   "Piedmont",   "Italy",    ["piemonte", "piemont"]),
    ("tuscany",    "Tuscany",    "Italy",    ["toscana", "toscan"]),
    ("rioja",      "Rioja",      "Spain",    ["rioja"]),
    ("port",       "Port & Douro", "Portugal", ["douro", "porto", "port"]),
    ("california", "California", "USA",      ["kalifornia", "california"]),
]

WINE_TYPES = ("punaviini", "valkoviini", "roseeviini", "kuohuviini", "samppanj",
              "jälkiruokaviini", "väkevöidyt", "väkevät viinit")


# ---------------------------------------------------------------- download & parse

def download(url=ALKO_URL):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) wine-index/1.0",
        "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    s = re.sub(r"[^0-9.]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def parse_alko(xlsx_bytes):
    import openpyxl  # pip install openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    header, rows = None, []
    for row in ws.iter_rows(values_only=True):
        cells = ["" if c is None else c for c in row]
        if header is None:
            if cells and str(cells[0]).strip() == "Numero":
                header = [str(c).strip() for c in cells]
            continue
        rec = dict(zip(header, cells))
        typ = str(rec.get("Tyyppi", "")).lower()
        if not any(t in typ for t in WINE_TYPES) or "juoma" in typ or "glögi" in typ:
            continue
        size = num(rec.get("Pullokoko"))
        price = num(rec.get("Hinta"))
        if not size or not price or size < 0.1:
            continue
        country_fi = str(rec.get("Valmistusmaa", "")).strip()
        rows.append({
            "id": str(rec.get("Numero", "")).strip(),
            "name": str(rec.get("Nimi", "")).strip(),
            "producer": str(rec.get("Valmistaja", "")).strip(),
            "size_l": size,
            "price": price,
            "country": COUNTRIES.get(country_fi.lower(), country_fi or "Unknown"),
            "region": str(rec.get("Alue", "")).strip(),
            "vintage": str(rec.get("Vuosikerta", "")).strip(),
            "type": str(rec.get("Tyyppi", "")).strip(),
        })
    if header is None:
        raise ValueError("Could not find the 'Numero' header row - has Alko changed the file format?")
    return rows


FIELDS = ["id", "name", "producer", "size_l", "price", "country", "region", "vintage", "type"]


def save_snapshot(rows, date):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAP_DIR / f"{date}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


def load_snapshots():
    snaps = []
    for p in sorted(SNAP_DIR.glob("*.csv")):
        with open(p, encoding="utf-8") as f:
            rows = []
            for r in csv.DictReader(f):
                r["size_l"] = float(r["size_l"]); r["price"] = float(r["price"])
                rows.append(r)
        snaps.append((p.stem, rows))
    return snaps


# ---------------------------------------------------------------- index maths

def p750(r):
    return r["price"] * 0.75 / r["size_l"]


def groups_for(r):
    """Every index a bottle belongs to."""
    out = ["all", "country:" + r["country"]]
    reg = r["region"].lower()
    for gid, _, country, keys in REGIONS:
        if r["country"] == country and any(k in reg for k in keys):
            out.append(gid)
    return out


def build():
    snaps = load_snapshots()
    if not snaps:
        print("No snapshots yet.", file=sys.stderr)
        return 1
    dates = [d for d, _ in snaps]
    keyed = [{(r["id"], r["size_l"]): r for r in rows} for _, rows in snaps]

    # discover groups
    names = {"all": ("All wine", "summary")}
    for gid, name, _, _ in REGIONS:
        names[gid] = (name, "region")
    counts = {}
    for r in snaps[-1][1]:
        for g in groups_for(r):
            counts[g] = counts.get(g, 0) + 1
    for g in counts:
        if g.startswith("country:"):
            names[g] = (g.split(":", 1)[1], "country")
    # keep countries with a meaningful number of bottles
    groups = [g for g in names if names[g][1] != "country" or counts.get(g, 0) >= 25]

    series = {g: {t: {"index": [100.0], "median": [], "count": [], "matched": [None]}
                  for t in ("all", "premium")} for g in groups}
    gset = set(groups)
    member_cache = [{k: [g for g in groups_for(r) if g in gset] for k, r in snap.items()} for snap in keyed]

    for i, cur in enumerate(keyed):
        prices = {(g, t): [] for g in groups for t in ("all", "premium")}
        logs = {(g, t): [] for g in groups for t in ("all", "premium")}
        prev = keyed[i - 1] if i else {}
        for k, r in cur.items():
            pc = p750(r)
            tiers_now = ("all", "premium") if pc >= PREMIUM_EUR else ("all",)
            rel = None
            if k in prev and prev[k]["price"] > 0:
                pp = p750(prev[k])
                rel = (math.log(pc / pp), ("all", "premium") if pp >= PREMIUM_EUR else ("all",))
            for g in member_cache[i][k]:
                for t in tiers_now:
                    prices[(g, t)].append(pc)
                if rel:
                    for t in rel[1]:
                        logs[(g, t)].append(rel[0])
        for g in groups:
            for t in ("all", "premium"):
                s, ps, ls = series[g][t], prices[(g, t)], logs[(g, t)]
                s["median"].append(round(statistics.median(ps), 2) if ps else None)
                s["count"].append(len(ps))
                if i == 0:
                    continue
                link = math.exp(sum(ls) / len(ls)) if len(ls) >= MIN_MATCHED else 1.0
                s["index"].append(round(s["index"][-1] * link, 3))
                s["matched"].append(len(ls))

    # latest bottles, with last-week and first-snapshot price for movers / constituents
    latest, prev = keyed[-1], (keyed[-2] if len(keyed) > 1 else {})
    year_ago = keyed[-53] if len(keyed) >= 53 else {}
    month_ago = keyed[-5] if len(keyed) >= 5 else keyed[0]
    bottles = []
    for k, r in latest.items():
        bottles.append({
            "n": r["name"], "p": r["producer"], "v": r["vintage"], "c": r["country"], "r": r["region"],
            "s": r["size_l"], "price": r["price"],
            "prev": prev[k]["price"] if k in prev else None,
            "yago": year_ago[k]["price"] if k in year_ago else None,
            "mago": month_ago[k]["price"] if k in month_ago and month_ago is not latest else None,
            "g": [g for g in groups_for(r) if g in series],
        })

    unmatched = {}
    for r in snaps[-1][1]:
        if r["country"] in ("France", "Italy", "Spain", "Portugal", "USA") and len(groups_for(r)) == 2:
            unmatched[f'{r["country"]} / {r["region"] or "(blank)"}'] = unmatched.get(
                f'{r["country"]} / {r["region"] or "(blank)"}', 0) + 1

    payload = {
        "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "Alko price list (alko.fi)",
        "dates": dates,
        "premiumEur": PREMIUM_EUR,
        "groups": [{"id": g, "name": names[g][0], "kind": names[g][1], "series": series[g]} for g in groups],
        "bottles": bottles,
        "unmatchedRegions": dict(sorted(unmatched.items(), key=lambda kv: -kv[1])[:40]),
    }
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text("window.WINE_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
                      encoding="utf-8")
    print(f"Built {len(groups)} indices over {len(dates)} snapshots -> {OUT_JS}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", help="use a price list you downloaded yourself")
    ap.add_argument("--date", help="snapshot date YYYY-MM-DD (default today)")
    ap.add_argument("--build-only", action="store_true")
    a = ap.parse_args()
    if not a.build_only:
        data = pathlib.Path(a.xlsx).read_bytes() if a.xlsx else download()
        rows = parse_alko(data)
        date = a.date or dt.date.today().isoformat()
        path = save_snapshot(rows, date)
        print(f"Saved {len(rows)} wines to {path}")
    return build()


if __name__ == "__main__":
    sys.exit(main())
