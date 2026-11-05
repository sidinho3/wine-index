"""Parsers for the extra price sources collected by tools/collect_regional.py.

Each parser returns rows shaped like the EU data:
  {"ms": country code, "wine": series name, "unit": "Euro / HL.", "date": "YYYY-MM-DD", "price": float}
"""
import pathlib
import re

RAW = pathlib.Path(__file__).resolve().parent / "data" / "raw"
MONTHS_FR = {m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                                         "août", "septembre", "octobre", "novembre", "décembre"], 1)}


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def franceagrimer():
    """Monthly French bulk prices (same eight series the EU publishes, but more current)."""
    f = RAW / "franceagrimer" / "cotation_ue.xls"
    if not f.exists():
        return []
    import xlrd
    sh = xlrd.open_workbook(str(f)).sheet_by_index(0)
    head = None
    for i in range(sh.nrows):
        if any(str(c).strip() == "Vin AOP" for c in sh.row_values(i)):
            head = i
            break
    if head is None:
        return []
    names = []
    colour = None
    top = sh.row_values(head - 1)
    for j, c in enumerate(sh.row_values(head)):
        if str(top[j]).strip():
            colour = str(top[j]).strip()
        names.append(f"{colour} / {str(c).strip()}" if str(c).strip() else None)
    rows, start_year = [], None
    for i in range(head + 1, sh.nrows):
        r = sh.row_values(i)
        camp = str(r[0]).strip()
        if re.match(r"\d{4}-\d{4}", camp):
            start_year = int(camp[:4])
        month = MONTHS_FR.get(str(r[1]).strip().lower())
        if not month or start_year is None:
            continue
        year = start_year if month >= 8 else start_year + 1
        for j in range(2, len(r)):
            p = num(r[j])
            if names[j] and p:
                rows.append({"ms": "FR", "wine": names[j], "unit": "Euro / HL.",
                             "date": f"{year}-{month:02d}-01", "price": p})
    return rows


# ---------------------------------------------------------------- Piedmont (Asti)

ASTI_SERIES = [  # (series name, pattern on the start of the line)
    ("Barbera d'Asti", r"barbera d.asti\b(?!.*superiore)"),
    ("Barbera del Monferrato", r"barbera del monferrato\b(?!.*superiore)"),
    ("Piemonte Barbera", r"piemonte (d\.?o\.?c\.? )?barbera"),
    ("Nizza", r"nizza\b"),
    ("Dolcetto d'Asti", r"dolcetto d.asti"),
    ("Grignolino d'Asti", r"grignolino d.asti"),
    ("Freisa d'Asti", r"freisa d.asti"),
    ("Ruchè", r"ruch[eè]"),
    ("Cortese dell'Alto Monferrato", r"cortese dell.alto monferrato"),
    ("Piemonte Chardonnay", r"piemonte (d\.?o\.?c\.? )?chardonnay"),
]
MESI = {m: i for i, m in enumerate(["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
                                    "agosto", "settembre", "ottobre", "novembre", "dicembre"], 1)}
NUM = r"(\d+,\d+)\*?"


def _median(v):
    v = sorted(v)
    n = len(v)
    return (v[n // 2] + v[(n - 1) // 2]) / 2


def asti():
    rows = []
    for f in sorted((RAW / "asti").glob("*.txt")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.stem)
        if m:
            date = m.group(1)
        else:
            m = re.search(r"(\d{1,2})-([a-z]+)-(\d{4})", f.stem.lower())
            if not m or m.group(2) not in MESI:
                continue
            date = f"{m.group(3)}-{MESI[m.group(2)]:02d}-{int(m.group(1)):02d}"
        found = {}
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            low = line.strip().lower()
            if not re.search(r"\blitro\b", low) or low.startswith(("mosto", "barbera atta", "uve")):
                continue
            nums = [float(x.replace(",", ".")) for x in re.findall(NUM, line.split("itro", 1)[1])]
            if len(nums) < 2:
                continue
            lo, hi = nums[-2], nums[-1]          # the latest period's min and max
            if not (0.2 <= lo <= hi <= 30):
                continue
            for name, pat in ASTI_SERIES:
                if re.match(pat, low):
                    found.setdefault(name, []).append((lo + hi) / 2 * 100)   # €/litre -> €/hl
                    break
        for name, vals in found.items():
            rows.append({"ms": "IT", "wine": name + " (Asti)", "unit": "Euro / HL.", "date": date,
                         "price": round(_median(vals), 2), "region": "Piedmont"})
    return rows


# ---------------------------------------------------------------- Tuscany (Florence)

FI_SERIES = [
    ("Chianti Classico", r"chianti classico"),
    ("Chianti", r"chianti\b"),
    ("Toscano rosso", r"(vino )?toscano rosso"),
    ("Toscano Sangiovese", r"(vino )?toscano sangiovese"),
    ("Toscano bianco", r"(vino )?toscano bianco"),
]


def firenze():
    rows = []
    for f in sorted((RAW / "firenze").glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(\d{1,2})[./](\d{1,2})[./](20\d{2})\s*$", text[:3000], re.M) or \
            re.search(r"al\s+(\d{1,2})[./](\d{1,2})[./](20\d{2})", text[:3000])
        if m:
            date = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        else:  # fall back to the list number: week n of the year
            y, n = f.stem.split("-")[:2]
            import datetime as dt
            date = (dt.date(int(y), 1, 1) + dt.timedelta(weeks=int(n) - 1)).isoformat()
        found = {}
        for line in text.splitlines():
            mm = re.match(r"\s*\d+\s+(.+?)\s+(?:19|20)\d{2}\s+hl\.\s+([\d.]+,\d+)\s+([\d.]+,\d+)", line, re.I)
            if not mm:
                continue
            low = mm.group(1).strip().lower()
            lo, hi = num(mm.group(2)), num(mm.group(3))
            if not lo or not hi or not (20 <= lo <= hi <= 3000):
                continue
            for name, pat in FI_SERIES:
                if re.match(pat, low):
                    found.setdefault(name, []).append((lo + hi) / 2)
                    break
        for name, vals in found.items():
            rows.append({"ms": "IT", "wine": name + " (Florence)", "unit": "Euro / HL.", "date": date,
                         "price": round(_median(vals), 2), "region": "Tuscany"})
    return rows


def all_rows():
    out = []
    for fn in (franceagrimer, asti, firenze):
        try:
            out += fn()
        except Exception as e:  # a broken source must not break the whole build
            print(f"warning: {fn.__name__} failed: {e}")
    return out


if __name__ == "__main__":
    import collections
    rows = franceagrimer()
    c = collections.defaultdict(list)
    for r in rows:
        c[r["wine"]].append(r["date"])
    for k, v in c.items():
        print(k, min(v), max(v), len(v))
