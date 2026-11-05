"""Temporary helper: fetch pages from GitHub's network and save them under raw/ for inspection."""
import http.cookiejar, pathlib, re, urllib.parse, urllib.request
OUT = pathlib.Path("raw"); OUT.mkdir(exist_ok=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
op.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) wine-index research")]
def get(u, data=None):
    try:
        with op.open(u, data=data, timeout=60) as r:
            b = r.read(); final = r.geturl()
    except Exception as e:
        print("ERR", u, e); return b""
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", u)[-120:]
    (OUT / name).write_bytes(b)
    print("OK ", len(b), final)
    return b
for u in ["https://visionet.franceagrimer.fr/",
          "https://visionet.franceagrimer.fr/Pages/Statistiques.aspx?menuurl=Statistiques%2Fproductions%20vegetales%2Fvin%20et%20cidriculture%2Fprix%20moyens%2Fprix%20moyens%20vrac%20VSIG%20et%20IGP",
          "https://visionet.franceagrimer.fr/Pages/SeriesChronologiques.aspx?menuurl=SeriesChronologiques/productions%20vegetales/vin%20et%20cidriculture/prix%20moyens/prix%20moyens%20vrac%20communiqu%C3%A9s%20%C3%A0%20la%20Commission%20europ%C3%A9enne"]:
    b = get(u)
    for h in sorted(set(re.findall(rb'href="([^"]+\.(?:xlsx?|csv|zip|pdf)[^"]*)"', b, re.I)))[:40]:
        print("   FILE", h.decode(errors="replace"))
