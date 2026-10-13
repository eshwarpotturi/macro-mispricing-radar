"""Forecast errors: forecast minus the first published actual (from the same forecaster's first release after the year ends;
falls back to the IMF's first actual). Writes data/errors.csv. h = target year - release year."""
import csv
from collections import defaultdict
F = list(csv.DictReader(open("data/forecasts.csv")))
for r in F: r["year"] = int(r["year"]); r["value"] = float(r["value"]); r["ry"] = int(r["release"][:4])
# first actual per (forecaster, country, var, year): value in the earliest release dated after the year
first = {}
for r in sorted(F, key=lambda r: r["release"]):
    if r["ry"] > r["year"]:
        first.setdefault((r["forecaster"], r["country"], r["var"], r["year"]), r["value"])
out = []
for r in F:
    if r["ry"] > r["year"] or r["year"] in (2020, 2021): continue
    k = (r["forecaster"], r["country"], r["var"], r["year"])
    a = first.get(k, first.get(("IMF",) + k[1:]))
    if a is None: continue
    out.append({"forecaster": r["forecaster"], "release": r["release"], "country": r["country"], "var": r["var"],
                "year": r["year"], "h": r["year"] - r["ry"], "forecast": r["value"], "actual": a, "err": round(r["value"] - a, 4)})
with open("data/errors.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out), "errors")
