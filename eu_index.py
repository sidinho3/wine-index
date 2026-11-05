#!/usr/bin/env python3
"""Build Liv-ex-style indices from the EU bulk wine price history.

Reads data/eu/prices.json (from eu_fetch.py) and writes site/eu-data.js for site/eu.html.

The EU publishes about one price per month for each wine series (a member state +
area + wine class, in euros per hectolitre). Method:
  * one observation per series per month (the last one published that month),
    smoothed with the median of the series' last 3 prices to remove one-off spikes;
  * a composite index is the geometric mean (equal weights) of its series, each
    scaled so that when it joins it sits exactly at the index level of that month,
    so new series don't cause jumps; a series' last price is carried forward for up
    to 6 months to bridge gaps;
  * every index starts at 100 in its first month.
"""
import datetime as dt
import json
import math
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "data" / "eu" / "prices.json"
OUT = ROOT / "site" / "eu-data.js"
CARRY = 6                # months a series' last price is carried forward
MIN_MONTHS = 12          # ignore series with fewer monthly prices than this
COUNTRY = {"FR": "France", "IT": "Italy", "ES": "Spain", "DE": "Germany"}


def tier(ms, wine):
    w = wine.lower()
    if re.search(r"sans ig|sin dop|senza dop", w):
        return "No GI"
    if re.search(r"\b(aop|dop)\b", w) or "qba" in w:
        return "PDO"
    if re.search(r"\bigp\b", w):
        return "PGI"
    return None


def colour(wine):
    w = wine.lower()
    if re.search(r"rouge|tinto|rosso|\brot\b", w):
        return "Red"
    if re.search(r"blanc|blanco|bianco|weiß|weiss", w):
        return "White"
    return None


def area(ms, wine):
    if ms == "FR":
        return "France (national)"
    m = re.match(r"([A-ZÄÖÜ][\wäöüß]+(?: [A-Z][\w]+)?)", wine)
    return m.group(1) if m else wine


def mi(m):  # "YYYY-MM" -> month number
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def label(m):
    return f"{m}"


def main():
    rows = json.loads(SRC.read_text(encoding="utf-8"))["rows"]
    series = {}
    for r in rows:
        key = f'{r["ms"]}|{r["wine"]}'
        s = series.setdefault(key, {"ms": r["ms"], "wine": r["wine"], "unit": r["unit"], "obs": {}})
        if r["price"] and r["price"] > 0:
            s["obs"][r["date"][:7]] = r["price"]
    series = {k: s for k, s in series.items() if len(s["obs"]) >= MIN_MONTHS}
    # The raw series contain one-off spikes (e.g. a single month at half or double the
    # usual price). Smooth each series with the median of its last 3 published prices.
    for s in series.values():
        ks = sorted(s["obs"])
        s["raw"] = dict(s["obs"])
        s["obs"] = {m: statistics.median([s["raw"][x] for x in ks[max(0, i - 2): i + 1]]) for i, m in enumerate(ks)}

    first = min(min(s["obs"]) for s in series.values())
    last = max(max(s["obs"]) for s in series.values())
    months = []
    m = mi(first)
    while m <= mi(last):
        months.append(f"{m // 12}-{m % 12 + 1:02d}")
        m += 1

    for k, s in series.items():
        s["tier"], s["colour"], s["area"] = tier(s["ms"], s["wine"]), colour(s["wine"]), area(s["ms"], s["wine"])
        s["country"] = COUNTRY.get(s["ms"], s["ms"])

    defs = [("all", "All EU bulk wine", "summary", lambda s: True)]
    for code, name in COUNTRY.items():
        defs.append((code.lower(), name, "country", lambda s, c=code: s["ms"] == c))
    for t in ("PDO", "PGI", "No GI"):
        defs.append(("tier-" + t.lower().replace(" ", ""), {"PDO": "Protected origin (AOP/DOP/QbA)",
                     "PGI": "Geographical indication (IGP)", "No GI": "No geographical indication"}[t],
                     "tier", lambda s, t=t: s["tier"] == t))
    for c in ("Red", "White"):
        defs.append(("col-" + c.lower(), c + " wine", "colour", lambda s, c=c: s["colour"] == c))
    for k, s in series.items():
        defs.append(("s:" + k, f'{s["wine"]}', "series", lambda x, k=k: x is series[k]))

    groups = []
    for gid, name, kind, pred in defs:
        mem = [s for s in series.values() if pred(s)]
        if not mem:
            continue
        # carry each series' last smoothed price forward for up to CARRY months
        val = {}
        for s in mem:
            v, last_i, row = None, None, []
            for i, mth in enumerate(months):
                if mth in s["obs"]:
                    v, last_i = s["obs"][mth], i
                row.append(v if last_i is not None and i - last_i <= CARRY else None)
            val[id(s)] = row
        # fixed-base index: each series is scaled so that, in the month it joins,
        # it sits at the index level of the series already present (no chain drift)
        idx, cnt, scale = [], [], {}
        for i, mth in enumerate(months):
            cnt.append(sum(1 for s in mem if mth in s["obs"]))
            avail = [s for s in mem if val[id(s)][i] is not None]
            known = [s for s in avail if id(s) in scale]
            if known:
                level = math.exp(sum(math.log(val[id(s)][i] * scale[id(s)]) for s in known) / len(known))
            else:
                level = 100.0 if avail else None
            for s in avail:
                if id(s) not in scale:
                    scale[id(s)] = level / val[id(s)][i]
            if avail and len(known) < len(avail):
                level = math.exp(sum(math.log(val[id(s)][i] * scale[id(s)]) for s in avail) / len(avail))
            idx.append(round(level, 3) if level is not None else None)
        # trim leading/trailing empty months for this group
        start = next(i for i, v in enumerate(idx) if v is not None)
        end = max(i for i, c in enumerate(cnt) if c) + 1
        groups.append({
            "id": gid, "name": name, "kind": kind, "start": start, "end": end,
            "index": idx[start:end], "count": cnt[start:end],
            "members": [f'{s["ms"]}|{s["wine"]}' for s in mem],
        })

    comp = []
    for k, s in series.items():
        ms_sorted = sorted(s["obs"])
        comp.append({"id": k, "ms": s["ms"], "country": s["country"], "wine": s["wine"], "unit": s["unit"],
                     "tier": s["tier"], "colour": s["colour"], "first": ms_sorted[0], "last": ms_sorted[-1],
                     "months": len(ms_sorted), "prices": {m: s["raw"][m] for m in ms_sorted}})

    payload = {
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "fetched": json.loads(SRC.read_text(encoding="utf-8")).get("fetched"),
        "months": months, "groups": groups, "series": comp,
        "source": "European Commission, Agri-food Data Portal: wine prices",
        "sourceUrl": "https://agridata.ec.europa.eu/extensions/DataPortal/wine.html",
    }
    OUT.write_text("window.EU_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    print(f"{len(series)} series, {len(groups)} indices, {months[0]} to {months[-1]} -> {OUT}")
    for g in groups:
        if g["kind"] != "series":
            print(f'  {g["name"]:<40} {months[g["start"]]}..{months[g["start"] + len(g["index"]) - 1]}  '
                  f'{g["index"][-1]:7.1f}  ({max(g["count"])} series)')
    return 0


if __name__ == "__main__":
    sys.exit(main())
