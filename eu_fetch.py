#!/usr/bin/env python3
"""Download the full EU wine price history (European Commission Agri-food Data Portal).

Writes data/eu/prices.json: every weekly record for every member state and wine class.
Free, no key. Docs: https://agridata.ec.europa.eu/extensions/API_Documentation/wine.html
"""
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.tech.ec.europa.eu/agrifood/api/wine"
OUT = pathlib.Path(__file__).resolve().parent / "data" / "eu" / "prices.json"


def get(path, **params):
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "wine-index"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []          # no data for that period
            if e.code != 429 or attempt == 5:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 15 * (attempt + 1)
            print(f"rate limited, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)


def iso(s):
    for f in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except (TypeError, ValueError):
            pass
    return None


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("€", "").replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def main():
    rows = []
    # pull year by year so no single response is huge
    for year in range(2000, dt.date.today().year + 1):
        time.sleep(3)
        try:
            recs = get("prices", years=year)
        except Exception as e:
            print(f"{year}: failed {e}", file=sys.stderr)
            continue
        n = 0
        for r in recs:
            p, d = num(r.get("price")), iso(r.get("endDate")) or iso(r.get("beginDate"))
            if p is None or d is None:
                continue
            rows.append({"ms": r.get("memberStateCode"), "msName": r.get("memberStateName"),
                         "wine": (r.get("description") or "").strip(), "unit": r.get("unit") or "",
                         "date": d, "week": r.get("weekNumber"), "price": p})
            n += 1
        print(f"{year}: {n} records")
    if not rows:
        print("No data fetched", file=sys.stderr)
        return 1
    rows.sort(key=lambda r: (r["ms"], r["wine"], r["date"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"fetched": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "rows": rows},
                              ensure_ascii=False, separators=(",", ":")))
    # coverage summary for the log
    cov = {}
    for r in rows:
        k = (r["ms"], r["wine"], r["unit"])
        a = cov.setdefault(k, [r["date"], r["date"], 0])
        a[0] = min(a[0], r["date"]); a[1] = max(a[1], r["date"]); a[2] += 1
    for k, (a, b, n) in sorted(cov.items()):
        print(f"{k[0]} | {k[1]} | {k[2]} | {a} -> {b} | {n} weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
