#!/usr/bin/env python3
"""Download the free regional bulk wine price bulletins and keep their text.

Sources (all public bulletins, fetched politely, one request per second):
  asti    - Camera di Commercio Alessandria-Asti, weekly wine quotations (Piedmont)
  firenze - Camera di Commercio di Firenze, weekly wholesale price list (Tuscany)
  rioja   - Gobierno de La Rioja, weekly agricultural price sheet (Rioja)
  franceagrimer - FranceAgriMer monthly French bulk prices reported to the EU (more
            up to date than the EU's own API); the latest workbook is kept as-is

Each PDF is converted with `pdftotext -layout` and saved as text under
data/raw/<source>/; files already saved are skipped, so reruns only fetch new weeks.
"""
import http.cookiejar
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
UA = "Mozilla/5.0 (X11; Linux x86_64) wine-index/1.0 (personal price index)"
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
opener.addheaders = [("User-Agent", UA)]


def get(url):
    time.sleep(1)
    with opener.open(url, timeout=90) as r:
        return r.read()


def links(base, html, pattern):
    out = []
    for h in re.findall(rb'href="([^"#]+)"', html):
        u = urllib.parse.urljoin(base, h.decode("utf-8", "replace").replace("&amp;", "&"))
        if re.search(pattern, u, re.I):
            out.append(u)
    return list(dict.fromkeys(out))


def save_pdf_text(src, name, url, quiet=False):
    out = RAW / src / (name + ".txt")
    if out.exists():
        return False
    try:
        pdf = get(url)
    except Exception as e:
        if not quiet:
            print(f"  skip {url}: {e}")
        return False
    if not pdf.startswith(b"%PDF"):
        print(f"  not a PDF: {url}")
        return False
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf); f.flush()
        txt = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True).stdout
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"SOURCE " + url.encode() + b"\n" + txt)
    return True


def asti():
    n = 0
    base = ("https://www.aa.camcom.it/prezzi-indici-analisi-economica-e-rilevazioni-statistiche/"
            "prezzi-e-indici-della-provincia-di-asti/quotazioni-dei-vini-arretrati")
    page2 = "https://www.aa.camcom.it/prezzi-indici-analisi-economica-e-rilevazioni-statistiche/prezzi-e-indici-della-provincia-di-asti"
    vini = links(base, get(base), r"/Vini_\d{8}_\d+\.pdf$") + links(page2, get(page2), r"/Vini_\d{8}_\d+\.pdf$")
    for u in dict.fromkeys(vini):
        d = re.search(r"Vini_(\d{8})", u).group(1)
        n += save_pdf_text("asti", f"{d[:4]}-{d[4:6]}-{d[6:]}", u)
    # newer lists are posted as news items
    pages = [f"https://www.aa.camcom.it/notizie?page={p}" for p in range(0, 40)]
    pages += [f"https://www.aa.camcom.it/search/node?keys=prezzi%20del%20vino&page={p}" for p in range(0, 10)]
    for s in pages:
        try:
            html = get(s)
        except Exception as e:
            print("  news page failed", e); break
        for item in links(s, html, r"/notizie/.*(vin|uve)"):
            for p in links(item, get(item), r"Listino%20prezzi%20VINO.*\.pdf$"):
                name = urllib.parse.unquote(p.rsplit("/", 1)[1]).replace(".pdf", "")
                n += save_pdf_text("asti", "news-" + re.sub(r"[^A-Za-z0-9]+", "-", name), p)
    print(f"asti: {n} new")


def firenze():
    n = 0
    base = "https://www.fi.camcom.gov.it/tutela-di-consumatori-e-imprese/prezzi/listini-settimanali-dei-prezzi-allingrosso"
    for u in links(base, get(base), r"listino.*\.pdf$"):
        name = urllib.parse.unquote(u.rsplit("/", 1)[1])
        m = re.search(r"n\.\s*(\d+)\s*-\s*(\d{4})", name)
        if not m or re.search(r"petrol", name, re.I):
            continue
        n += save_pdf_text("firenze", f"{m.group(2)}-{int(m.group(1)):02d}", u)
    # older lists (2013-2020) are no longer linked, but still sit at predictable addresses
    for year in range(2013, 2021):
        for k in range(1, 54):
            name = f"{year}-{k:02d}"
            if (RAW / "firenze" / (name + ".txt")).exists() or (RAW / "firenze" / ".missing" / name).exists():
                continue
            ok = False
            for pat in (f"listino%20n.%20{k}%20-%20{year}.pdf", f"listino%20n.%20{k}%20-{year}.pdf",
                        f"listino%20n.%20%20{k}%20-%20{year}.pdf"):
                if save_pdf_text("firenze", name, "https://www.fi.camcom.gov.it/sites/default/files/" + pat, quiet=True):
                    ok, n = True, n + 1
                    break
            if not ok:   # remember misses so later runs don't retry them
                (RAW / "firenze" / ".missing").mkdir(parents=True, exist_ok=True)
                (RAW / "firenze" / ".missing" / name).touch()
    print(f"firenze: {n} new")


def rioja():
    n = 0
    base = "https://www.larioja.org/agricultura/es/estadistica-agraria/observatorio-precios-agrarios/hoja-precios"
    years = links(base, get(base), r"hoja-precios-20\d\d$|observatorio-precios-agrarios-20\d\d$")
    for y in years:
        yr = re.search(r"(20\d\d)$", y).group(1)
        try:
            html = get(y)
        except Exception as e:
            print("  year failed", y, e); continue
        for p in links(y, html, r"\.pdf$"):
            name = urllib.parse.unquote(p.rsplit("/", 1)[1]).replace(".pdf", "")
            n += save_pdf_text("rioja", f"{yr}-" + re.sub(r"[^A-Za-z0-9]+", "-", name)[-60:], p)
    print(f"rioja: {n} new")


def franceagrimer():
    base = "https://visionet.franceagrimer.fr/Pages/"
    menu = ("SeriesChronologiques/productions vegetales/vin et cidriculture/prix moyens/"
            "prix moyens vrac communiqués à la Commission européenne")
    get(base + "Statistiques.aspx?sousmenu=productions%20vegetales")   # starts a session
    body = urllib.parse.urlencode({"niveau": "1", "dossierRacine": "SeriesChronologiques", "menuId": "",
                                   "menuTitre": menu.rsplit("/", 1)[1], "menuUrl": menu,
                                   "niveauMax": "False"}).encode()
    time.sleep(1)
    with opener.open(base + "SeriesChronologiquesDetail.aspx", data=body, timeout=90) as r:
        html = r.read()
    files = sorted(set(re.findall(rb'fileurl=([^"\'&<> ]+COTATION_UE[^"\'&<> ]*\.xls)', html)))
    if not files:
        print("franceagrimer: no files listed"); return
    latest = files[-1].decode()                      # names end in -Cyy-yy, so the last is newest
    data = get(base + "OpenDocument.aspx?fileurl=" + latest + "&telechargersanscomptage=oui")
    out = RAW / "franceagrimer" / "cotation_ue.xls"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.read_bytes() != data:
        out.write_bytes(data)
        print(f"franceagrimer: updated from {urllib.parse.unquote(latest).rsplit('/', 1)[1]}")
    else:
        print("franceagrimer: unchanged")


if __name__ == "__main__":
    for fn in (franceagrimer, asti, firenze, rioja):
        if len(sys.argv) > 1 and fn.__name__ not in sys.argv[1:]:
            continue
        try:
            fn()
        except Exception as e:
            print(f"{fn.__name__} failed: {e}")
