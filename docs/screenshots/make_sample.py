"""Build the screenshot sample: all 29 included + 271 random excluded records (with abstracts)
from Appenzeller-Herzog 2020 (CC-BY 4.0), plus 12 planted duplicates (6 exact copies with the
same DOI, 6 with a reformatted title and no DOI).  usage: python make_sample.py <work-dir>"""
import csv, gzip, io, json, random, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(io.StringIO(gzip.open(ROOT / "data/corpora/appenzeller_herzog_2020.csv.gz").read().decode("utf-8"))))
inc = [x for x in rows if x["label_included"] == "1"]
exc = [x for x in rows if x["label_included"] == "0" and x["abstract"].strip()]
rng = random.Random(20261003)
sample = inc + rng.sample(exc, 271); rng.shuffle(sample)
dups = []
for k, x in enumerate(rng.sample(sample, 12)):
    y = dict(x); y["record_id"] = x["record_id"] + "-dup"
    if k >= 6:
        y["title"] = " ".join(re.sub(r"[^a-z0-9 ]+", " ", x["title"].lower()).split()); y["doi"] = ""
    dups.append(y)
recs = sample + dups
with open(out / "wilson_sample.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["id", "title", "abstract", "authors", "year", "doi"])
    for x in recs:
        w.writerow([x["record_id"], x["title"], x["abstract"], x["authors"], x["year"], x["doi"].replace("https://dx.doi.org/", "")])
json.dump({x["record_id"]: int(x["label_included"]) for x in recs}, open(out / "gold.json", "w"))
print(len(recs), "records written to", out)
