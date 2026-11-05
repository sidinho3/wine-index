"""Temporary helper: probe FranceAgriMer VISIONet document listing."""
import http.cookiejar, pathlib, re, urllib.parse, urllib.request
OUT = pathlib.Path("raw"); OUT.mkdir(exist_ok=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
op.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) wine-index research")]
B = "https://visionet.franceagrimer.fr/Pages/"
def go(name, u, data=None):
    try:
        with op.open(u, data=urllib.parse.urlencode(data).encode() if data else None, timeout=60) as r:
            b = r.read()
        (OUT / name).write_bytes(b); print("OK ", name, len(b)); return b
    except Exception as e:
        print("ERR", name, e); return b""
go("home", B + "Statistiques.aspx?sousmenu=productions%20vegetales")
for page, root, url in [
    ("StatistiquesDetail.aspx", "Statistiques", "Statistiques/productions vegetales/vin et cidriculture/prix moyens/prix moyens vrac VSIG et IGP"),
    ("SeriesChronologiquesDetail.aspx", "SeriesChronologiques", "SeriesChronologiques/productions vegetales/vin et cidriculture/prix moyens/prix moyens vrac communiqués à la Commission européenne"),
    ("SeriesChronologiquesDetail.aspx", "SeriesChronologiques", "SeriesChronologiques/productions vegetales/vin et cidriculture/prix moyens"),
]:
    b = go(page + "_" + url.rsplit("/", 1)[1][:30], B + page, {"niveau": "1", "dossierRacine": root, "menuId": "", "menuTitre": url.rsplit("/", 1)[1], "menuUrl": url, "niveauMax": "False"})
    for m in sorted(set(re.findall(rb'fileurl="?([^"\' >]+)', b)) | set(re.findall(rb'(/[^"\' <>]+\.(?:xlsx?|csv|zip|pdf))', b, re.I)))[:30]:
        print("   FILE", m.decode(errors="replace"))
    print(b[:1500].decode(errors="replace").replace("\n", " ")[:1500])
