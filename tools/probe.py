"""Temporary helper: fetch pages from GitHub's network and save them under raw/ for inspection."""
import pathlib, re, sys, urllib.parse, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) wine-index research"}
OUT = pathlib.Path("raw"); OUT.mkdir(exist_ok=True)
seen = set()
def get(u):
    if u in seen: return b""
    seen.add(u)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
            b = r.read()
    except Exception as e:
        print("ERR", u, e); return b""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", u)[-150:]
    (OUT / name).write_bytes(b)
    print("OK ", len(b), u)
    return b
def links(base, b, pat):
    out = []
    for h in re.findall(rb'href="([^"#]+)"', b):
        h = urllib.parse.urljoin(base, h.decode(errors="replace").replace("&amp;", "&"))
        if re.search(pat, h, re.I): out.append(h)
    return sorted(set(out))
# FranceAgriMer VISIONet series page
get("https://visionet.franceagrimer.fr/Pages/SeriesChronologiques.aspx?menuurl=SeriesChronologiques/productions%20vegetales/vin%20et%20cidriculture/prix%20moyens/prix%20moyens%20vrac%20communiqu%C3%A9s%20%C3%A0%20la%20Commission%20europ%C3%A9enne")
b = get("https://www.data.gouv.fr/api/1/datasets/historique-de-la-campagne-viticulture-au-format-tableur/")
# La Rioja weekly price sheets
base = "https://www.larioja.org/agricultura/es/estadistica-agraria/observatorio-precios-agrarios/hoja-precios"
b = get(base)
for l in links(base, b, r"hoja-precios-20(2[3-6])")[:6]:
    bb = get(l)
    for p in links(l, bb, r"\.pdf")[-2:]:
        get(p)
# Florence chamber of commerce
for u in ["https://www.fi.camcom.gov.it/", "https://www.fi.camcom.gov.it/search/node?keys=listino"]:
    b = get(u)
    for l in links(u, b, r"listin|prezz")[:15]:
        bb = get(l)
        for p in links(l, bb, r"listino.*\.pdf|listin")[:10]:
            print("   CAND", p)
# Asti / Alessandria chamber of commerce
for u in ["https://www.aa.camcom.it/", "https://www.aa.camcom.it/search/node?keys=vini"]:
    b = get(u)
    for l in links(u, b, r"listin|prezz|pricelist")[:15]:
        bb = get(l)
        for p in links(l, bb, r"vini.*\.pdf|pricelist")[:10]:
            print("   CAND", p)
