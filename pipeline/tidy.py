"""Turns data/raw into data/forecasts.csv: one row per (forecaster, release, country, variable, target year).
Variables: gdp (real growth %), inflation (CPI %), fiscal (govt net lending % GDP), short_rate (%).
Run from the repo root: python pipeline/tidy.py"""
import csv, glob, io, json, os, re, zipfile

C = ["USA","CAN","GBR","DEU","FRA","ITA","ESP","NLD","CHE","SWE","JPN","AUS","KOR","CHN","HKG","IND","SGP",
     "IDN","MYS","THA","PHL","VNM","BRA","MEX","CHL","ZAF","SAU","TUR","POL"]
rows = []

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

# IMF WEO: release date = YYYY-MM-15 of the vintage
IMFV = {"NGDP_RPCH": "gdp", "PCPIPCH": "inflation", "GGXCNL_NGDP": "fiscal"}
for f in sorted(glob.glob("data/raw/imf_weo/WEO_*.json")):
    rel = re.search(r"(\d{4}-\d{2})", f).group(1) + "-15"
    for s in json.load(open(f)):
        d = s["dimensions"]; var = IMFV.get(d.get("weo-subject"))
        if not var: continue
        for p, v in zip(s["period"], s["value"]):
            if num(v) is not None: rows.append(("IMF", rel, d["weo-country"], var, int(p), num(v)))

# OECD Economic Outlook: release month by EO number
EOMONTH = {"114": "2023-11", "115": "2024-05", "116": "2024-12", "117": "2025-06", "118": "2025-12", "119": "2026-06"}
OECDV = {"GDPV_ANNPCT": "gdp", "CPI_YTYPCT": "inflation", "NLGQ": "fiscal", "IRS": "short_rate"}
for f in sorted(glob.glob("data/raw/oecd_eo/*.json")):
    ss = json.load(open(f))
    if not ss: continue
    name = ss[0].get("dataset_name", "")
    m = re.search(r"(?:No\.?\s*)?(1\d\d)", name)
    if not m: continue
    rel = EOMONTH.get(m.group(1))
    if not rel: continue
    for s in ss:
        d = s["dimensions"]; area = d.get("REF_AREA") or d.get("LOCATION"); var = OECDV.get(d.get("MEASURE") or d.get("VARIABLE"))
        if area not in C or not var or (d.get("FREQ") or d.get("FREQUENCY")) != "A": continue
        for p, v in zip(s["period"], s["value"]):
            if num(v) is not None and re.fullmatch(r"\d{4}", str(p)): rows.append(("OECD", rel + "-15", area, var, int(p), num(v)))

# EC AMECO forecast archive: real GDP growth from OVGD levels, HICP/CPI inflation, govt net lending
SEASON = {"winter": "02", "spring": "05", "autumn": "11"}
AM = {"OVGD": "gdp_level", "ZCPIH": "inflation_idx", "ZCPIN": "cpi_idx", "UBLGE": "fiscal", "UBLG": "fiscal"}
for f in sorted(glob.glob("data/raw/ameco/files/*.zip")):
    b = os.path.basename(f).lower()
    m = re.search(r"(winter|spring|autumn)[_-]?(\d{4})|(\d{4})[_-](winter|spring|autumn)", b)
    if not m: continue  # ameco0.zip = current release, covered by the newest vintage
    season, yr = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
    rel = f"{yr}-{SEASON[season]}-15"
    try:
        z = zipfile.ZipFile(f); z.testzip()
    except Exception:
        print('  skipping damaged', f); continue
    levels = {}
    for n in z.namelist():
        if not n.upper().endswith(".TXT"): continue
        r = csv.reader(io.StringIO(z.read(n).decode("latin-1")), delimiter=";")
        head = next(r, None)
        if not head: continue
        years = [(i, int(h)) for i, h in enumerate(head) if re.fullmatch(r"\d{4}", h.strip())]
        for line in r:
            if not line: continue
            parts = line[0].split(".")
            if len(parts) < 6 or parts[0] not in C: continue
            code, unit = parts[-1], parts[1:5]
            if code not in AM: continue
            if code == "OVGD" and parts[1:5] != ["1", "1", "0", "0"]: continue
            if code in ("ZCPIH", "ZCPIN") and parts[2:5] != ["0", "0", "0"]: continue
            if code in ("UBLGE", "UBLG") and parts[3] != "319": continue
            vals = {y: num(line[i].strip()) for i, y in years if i < len(line)}
            levels[(parts[0], code)] = vals
    for (c, code), vals in levels.items():
        if code == "UBLG" and (c, "UBLGE") in levels: continue
        if code in ("UBLGE", "UBLG"):
            for y, v in vals.items():
                if v is not None: rows.append(("EC", rel, c, "fiscal", y, v))
            continue
        var = "gdp" if code == "OVGD" else "inflation"
        if code == "ZCPIN" and (c, "ZCPIH") in levels: continue
        for y, v in vals.items():
            p = vals.get(y - 1)
            if v is not None and p: rows.append(("EC", rel, c, var, y, round(100 * (v / p - 1), 3)))

os.makedirs("data", exist_ok=True)
with open("data/forecasts.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["forecaster", "release", "country", "var", "year", "value"]); w.writerows(rows)
from collections import Counter
print(len(rows), "rows"); print(Counter((r[0], r[3]) for r in rows))
print("releases:", {k: len(v) for k, v in __import__("itertools").groupby(sorted(set((r[0], r[1]) for r in rows)), key=lambda x: x[0]) for v in [list(v)]})
