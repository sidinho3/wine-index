"""Temporary helper: list and download FranceAgriMer VISIONet wine price files."""
import http.cookiejar, pathlib, re, urllib.parse, urllib.request
OUT = pathlib.Path("raw"); OUT.mkdir(exist_ok=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
op.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) wine-index research")]
B = "https://visionet.franceagrimer.fr/Pages/"
def go(u, data=None):
    with op.open(u, data=urllib.parse.urlencode(data).encode() if data else None, timeout=90) as r:
        return r.read()
go(B + "Statistiques.aspx?sousmenu=productions%20vegetales")
for root, url in [("Statistiques", "Statistiques/productions vegetales/vin et cidriculture/prix moyens/prix moyens vrac VSIG et IGP"),
                  ("SeriesChronologiques", "SeriesChronologiques/productions vegetales/vin et cidriculture/prix moyens/prix moyens vrac communiqués à la Commission européenne")]:
    try:
        b = go(B + "SeriesChronologiquesDetail.aspx", {"niveau": "1", "dossierRacine": root, "menuId": "", "menuTitre": url.rsplit("/", 1)[1], "menuUrl": url, "niveauMax": "False"})
    except Exception as e:
        print("ERR list", root, e); continue
    files = sorted(set(m.decode() for m in re.findall(rb'fileurl=([^"\'&<> ]+\.(?:xlsx?|csv|zip))', b, re.I)))
    print(root, len(files), "files")
    for f in files:
        name = urllib.parse.unquote(f).rsplit("/", 1)[1]
        print("  ", name)
        try:
            data = go(B + "OpenDocument.aspx?fileurl=" + f + "&telechargersanscomptage=oui")
            (OUT / name).write_bytes(data); print("     saved", len(data), data[:8])
        except Exception as e:
            print("     ERR", e)
