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


def all_rows():
    out = []
    for fn in (franceagrimer,):
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
