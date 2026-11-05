"""Temporary helper: fetch a few URLs from GitHub's network and print what comes back."""
import json, sys, urllib.request
UA = {"User-Agent": "Mozilla/5.0 wine-index research"}
def get(u, n=3000):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
            b = r.read()
            print(f"\n=== {u}\nHTTP {r.status} {r.headers.get('content-type')} {len(b)} bytes")
            return b
    except Exception as e:
        print(f"\n=== {u}\nERROR {e}")
        return b""
b = get("https://www.data.gouv.fr/api/1/datasets/?q=prix+moyens+vrac+VSIG+IGP&page_size=6")
try:
    for x in json.loads(b)["data"]:
        print("DATASET", x["title"], x["page"])
        for r in x["resources"]:
            print("   RES", r["title"], r["format"], r["url"], r.get("last_modified"))
except Exception as e:
    print("parse error", e)
for u in ["https://www.fi.camcom.gov.it/listini-prezzi", "https://www.fi.camcom.gov.it/content/listino-prezzi-settimanale",
          "https://www.aa.camcom.it/listini-prezzi", "https://www.larioja.org/agricultura/es/estadistica-agraria/observatorio-precios-agrarios/hoja-precios"]:
    b = get(u)
    import re
    links = sorted(set(re.findall(rb'href="([^"]+?\.(?:pdf|xlsx?|csv)[^"]*)"', b)))
    for l in links[:40]:
        print("   LINK", l.decode(errors="replace"))
