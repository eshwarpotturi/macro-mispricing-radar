"""Builds index.html (GitHub Pages) from site/template.html + data/page_data.json. Run from repo root."""
import json
d = json.load(open("data/page_data.json"))
t = open("site/template.html", encoding="utf-8").read()
open("index.html", "w", encoding="utf-8").write(t.replace("/*DATA*/", json.dumps(d, separators=(",", ":")), 1))
print("built index.html")
