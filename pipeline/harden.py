"""Adds the European Commission (AMECO archive, 2011-2025) as a forecaster with real history, on top of the page data
Eswar built (IMF, OECD, World Bank). Recomputes the next-year consensus, its correction, the next-year 'growth forecasts
too rosy' signal, and the 'which forecaster to trust' comparison. Reads data/page_data_base.json, writes data/page_data.json.
Run from the repo root after tidy.py and errors.py."""
import csv, json, statistics as st
from collections import defaultdict

D = json.load(open("data/page_data_base.json"))
F = list(csv.DictReader(open("data/forecasts.csv")))
E = list(csv.DictReader(open("data/errors.csv")))
TARGET = 2027
SHRINK = lambda n: n / (n + 4)          # same rule as the IMF/OECD/WB corrections on the page
EC = "EC"
codes = [m["code"] for m in D["markets"]]

# Latest EC release with a TARGET-year GDP forecast
ecf = [r for r in F if r["forecaster"] == EC and r["var"] == "gdp" and int(r["year"]) == TARGET]
ec_rel = max(r["release"] for r in ecf)
ec_now = {r["country"]: float(r["value"]) for r in ecf if r["release"] == ec_rel}

# EC usual one-year-ahead error per country: autumn release for next year (h=1), one per target year
ec_err = defaultdict(list)
for r in E:
    if r["forecaster"] == EC and r["var"] == "gdp" and int(r["h"]) == 1 and r["release"][5:7] == "11":
        ec_err[r["country"]].append(float(r["err"]))

for c in codes:
    cs = D["consensus"].get(c)
    if cs is None or c not in ec_now: continue
    errs = ec_err.get(c, [])
    n = len(errs); ue = round(st.mean(errs) * SHRINK(n), 2) if n else 0.0
    cs["by"][EC] = {"forecast": round(ec_now[c], 2), "usual_error": ue, "n": n, "corrected": round(ec_now[c] - ue, 2)}
    fc = [v["forecast"] for v in cs["by"].values()]; co = [v["corrected"] for v in cs["by"].values()]
    cs["consensus"], cs["corrected"] = round(st.mean(fc), 2), round(st.mean(co), 2)
    cs["disappointment"] = round(cs["consensus"] - cs["corrected"], 2)

# Next-year 'growth forecasts too rosy' signal = expected disappointment; re-z-score across markets
H = D["signals"]["horizons"]["short"]
raw = {c: D["consensus"][c]["disappointment"] for c in codes if c in D["consensus"]}
mu, sd = st.mean(raw.values()), st.pstdev(raw.values()) or 1
H["today_raw"]["rosy_gdp"] = raw
H["today_z"]["rosy_gdp"] = {c: round((v - mu) / sd, 3) for c, v in raw.items()}

# Per-market detail: EC next-year forecast, EC usual error, EC column in the 2024-25 head-to-head
ec_by = {(r["country"], int(r["year"])): float(r["value"]) for r in F   # autumn release, one year ahead
         if r["forecaster"] == EC and r["var"] == "gdp" and r["release"][5:7] == "11" and int(r["year"]) == int(r["release"][:4]) + 1}
for m in D["markets"]:
    c = m["code"]
    if c in ec_now: m["next_year"][EC] = round(ec_now[c], 2)
    if ec_err.get(c): m["rosy_gdp_1y_ec"], m["n_gdp_ec"] = round(st.mean(ec_err[c]), 2), len(ec_err[c])
    for row in m["h2h"]:
        row[EC] = ec_by.get((c, row["year"]))

# 'Which forecaster to trust': short window (2024-25, all four) + long window (IMF vs EC on the same calls since 2012)
miss = [abs(r[EC] - r["actual"]) for m in D["markets"] for r in m["h2h"] if r.get(EC) is not None]
if miss: D["h2h_summary"][EC] = {"n": len(miss), "avg_miss": round(st.mean(miss), 2)}
imf = {(r["country"], int(r["year"])): float(r["err"]) for r in E
       if r["forecaster"] == "IMF" and r["var"] == "gdp" and int(r["h"]) == 1 and r["release"][5:7] == "10"}
ec = {(r["country"], int(r["year"])): float(r["err"]) for r in E
      if r["forecaster"] == EC and r["var"] == "gdp" and int(r["h"]) == 1 and r["release"][5:7] == "11"}
both = sorted(set(imf) & set(ec))
D["h2h_long"] = {"n": len(both), "markets": len({k[0] for k in both}), "first": min(k[1] for k in both), "last": max(k[1] for k in both),
                 "IMF": {"avg_miss": round(st.mean(abs(imf[k]) for k in both), 2), "bias": round(st.mean(imf[k] for k in both), 2)},
                 EC: {"avg_miss": round(st.mean(abs(ec[k]) for k in both), 2), "bias": round(st.mean(ec[k] for k in both), 2)},
                 "ec_closer": sum(abs(ec[k]) < abs(imf[k]) for k in both)}
D["ec_release"] = ec_rel
D["ec_releases"] = len({r["release"] for r in F if r["forecaster"] == EC})
D["n_forecasts_ec"] = sum(1 for r in F if r["forecaster"] == EC)
json.dump(D, open("data/page_data.json", "w"), indent=1)
print("EC release used:", ec_rel, "| markets with EC:", sum(c in ec_now for c in codes), "| h2h_long:", D["h2h_long"])
print("h2h_summary:", D["h2h_summary"])
