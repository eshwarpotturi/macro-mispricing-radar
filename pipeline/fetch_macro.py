"""Downloads raw macro forecast vintages into data/raw/. Run from the repo root on a laptop:
    python pipeline/fetch_macro.py
Safe to re-run: files already downloaded are skipped. Takes ~10-20 minutes.
Sources: IMF WEO vintages + OECD Economic Outlooks (via DBnomics), EC AMECO forecast archive,
World Bank (actual GDP, market cap/GDP, stock index), World Bank GEP and ADB ADO archive pages (for discovery)."""
import html, json, os, re, sys, time, urllib.parse, urllib.request
try:
    import truststore; truststore.inject_into_ssl()
except ImportError:
    sys.exit("pip install truststore  (needed for the corporate HTTPS certificate)")

RAW = "data/raw"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-script"}
C = ["USA","CAN","GBR","DEU","FRA","ITA","ESP","NLD","CHE","SWE","JPN","AUS","KOR","CHN","HKG","IND","SGP",
     "IDN","MYS","THA","PHL","VNM","BRA","MEX","CHL","ZAF","SAU","TUR","POL"]
LOG = []

def get(url, path=None, binary=False, tries=3):
    if path and os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path, "rb").read() if binary else open(path, encoding="utf-8").read()
    for i in range(tries):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
            if path:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "wb").write(b)
            return b if binary else b.decode("utf-8", "replace")
        except Exception as e:
            err = e; time.sleep(2 + 3 * i)
    LOG.append(f"FAIL {url} {err}"); print("  FAIL", url, str(err)[:80])
    return None

def dbn_series(provider, dataset, dims, path):
    """All series in a DBnomics dataset matching dims, with observations (paged)."""
    if os.path.exists(path): return
    out, off = [], 0
    while True:
        q = urllib.parse.urlencode({"dimensions": json.dumps(dims), "observations": 1, "limit": 500, "offset": off, "format": "json"})
        t = get(f"https://api.db.nomics.world/v22/series/{provider}/{urllib.parse.quote(dataset, safe='@')}?{q}")
        if not t: break
        j = json.loads(t); s = j.get("series", {}); docs = s.get("docs", [])
        out += docs; off += len(docs)
        if not docs or off >= s.get("num_found", 0): break
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w"))
    print(f"  {provider}/{dataset}: {len(out)} series")

def datasets(provider):
    codes, off = [], 0
    while True:
        j = json.loads(get(f"https://api.db.nomics.world/v22/datasets/{provider}?limit=500&offset={off}") or "{}")
        docs = j.get("datasets", {}).get("docs", [])
        codes += [d["code"] for d in docs]; off += len(docs)
        if not docs or off >= j.get("datasets", {}).get("num_found", 0): return codes

# 1. IMF WEO vintages (real GDP growth, CPI inflation, general govt net lending % GDP)
print("IMF WEO vintages")
weo = sorted(d for d in datasets("IMF") if re.fullmatch(r"WEO:\d{4}-\d{2}", d))
for d in weo:
    dbn_series("IMF", d, {"weo-country": C, "weo-subject": ["NGDP_RPCH", "PCPIPCH", "GGXCNL_NGDP"]}, f"{RAW}/imf_weo/{d.replace(':','_')}.json")

# 2. OECD Economic Outlook vintages on DBnomics (EO114 onward)
print("OECD Economic Outlooks")
eo = [d for d in datasets("OECD") if re.search(r"(^EO$|DSD_EO(_\d+)?@DF_EO(_\d+)?$)", d)]
for d in eo:
    v = ["GDPV_ANNPCT", "CPI_YTYPCT", "NLGQ", "IRS"]
    dims = {"LOCATION": C, "VARIABLE": v} if d == "EO" else {"REF_AREA": C, "MEASURE": v}
    dbn_series("OECD", d, dims, f"{RAW}/oecd_eo/{d.replace('@','_')}.json")

# 3. EC AMECO forecast archive: save the archive page and every zip it links to
print("AMECO archive")
page = get("https://economy-finance.ec.europa.eu/economic-research-and-databases/economic-databases/ameco-database/ameco-archive_en", f"{RAW}/ameco/archive_page.html")
if page:
    links = sorted(set(re.findall(r'href="([^"]+\.(?:zip|xlsx?|csv)(?:[?&][^"]*)?|[^"]*filename=[^"]+\.(?:zip|xlsx?|csv)[^"]*)"', page, re.I)))
    print(f"  {len(links)} files linked")
    for u in links:
        u = urllib.parse.urljoin("https://economy-finance.ec.europa.eu/", html.unescape(u))
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        name = qs.get("filename", [urllib.parse.unquote(urllib.parse.urlparse(u).path.rsplit("/", 1)[-1])])[0]
        name = re.sub(r'[\\/:*?"<>|]', "_", name)
        get(u, f"{RAW}/ameco/files/{name}", binary=True)

# 4. World Bank: actual GDP growth, GDP in USD, market cap % GDP, stock index change
print("World Bank indicators")
for ind in ["NY.GDP.MKTP.KD.ZG", "NY.GDP.MKTP.CD", "CM.MKT.LCAP.GD.ZS", "CM.MKT.INDX.ZG", "CM.MKT.LCAP.CD"]:
    get(f"https://api.worldbank.org/v2/country/{';'.join(C)}/indicator/{ind}?format=json&per_page=20000&date=1995:2026", f"{RAW}/worldbank/{ind}.json")

# 5. Discovery pages for World Bank GEP vintages and ADB Asian Development Outlook (parsed in step 2)
print("Discovery pages")
for name, u in {"gep_catalog": "https://datacatalog.worldbank.org/search/dataset/0037888/global-economic-prospects",
                "gep_api_sources": "https://api.worldbank.org/v2/sources?format=json&per_page=200",
                "adb_ado_data": "https://data.adb.org/taxonomy/term/123",
                "adb_editions": "https://www.adb.org/outlook/editions-old"}.items():
    get(u, f"{RAW}/discovery/{name}.html")

open(f"{RAW}/fetch_log.txt", "w").write("\n".join(LOG) or "no failures")
print("done;", len(LOG), "failures (see data/raw/fetch_log.txt)")
