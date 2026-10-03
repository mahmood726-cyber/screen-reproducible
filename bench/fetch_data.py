"""Fetch the 15 Cohen (2006) datasets and verify all 20 benchmark files by SHA-256.

The four SYNERGY datasets (CC-BY 4.0) and the Nagtegaal 2019 de-duplication dataset
(CC0) are redistributed in this repository. The Cohen 2006 files are NOT redistributed:
their inclusion labels are openly provided by OHSU (citation requested), but the
titles/abstracts are MEDLINE text whose redistribution terms we could not confirm. They
are downloaded from the ASReview `systematic-review-datasets` repository at a pinned
commit and checked byte-for-byte against data/SHA256SUMS. Any mismatch aborts the run.
"""
import gzip
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ROOT / "data" / "corpora"
PINNED_COMMIT = "38b35218e4d0f99621cec5a8a25a0147bb88c654"  # asreview/systematic-review-datasets, branch metadata-v1-final
BASE = f"https://raw.githubusercontent.com/asreview/systematic-review-datasets/{PINNED_COMMIT}/datasets/Cohen_2006/output/online/"


def expected_sums():
    out = {}
    for line in (ROOT / "data" / "SHA256SUMS").read_text().splitlines():
        h, name = line.split()
        out[name] = h
    return out


def sha(b):
    return hashlib.sha256(b).hexdigest()


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as e:  # bounded retry with backoff
            if k == tries - 1:
                raise
            print(f"  retry {k + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 ** k)


def main():
    sums = expected_sums()
    manifest = json.loads((CORPORA / "manifest.json").read_text(encoding="utf-8"))
    bad = []
    for d in manifest["datasets"]:
        gz = CORPORA / f"{d['id']}.csv.gz"
        if not gz.exists():
            if not d["id"].startswith("cohen_"):
                bad.append(f"{gz.name}: missing (should be in the repository)")
                continue
            topic = d["url"].rsplit("/", 1)[-1]
            raw = get(BASE + topic)
            if sha(raw) != sums[f"{d['id']}.csv"]:
                bad.append(f"{d['id']}: downloaded bytes do not match SHA256SUMS")
                continue
            with gzip.GzipFile(gz, "wb", mtime=0) as f:
                f.write(raw)
            print(f"  fetched {d['id']} ({len(raw):,} bytes, sha256 ok)")
        raw = gzip.open(gz).read()
        if sha(raw) != sums[f"{d['id']}.csv"]:
            bad.append(f"{d['id']}: sha256 mismatch")
    nag = ROOT / "data" / "dedup" / "nagtegaal_2019.csv"
    if sha(nag.read_bytes()) != sums["nagtegaal_2019.csv"]:
        bad.append("nagtegaal_2019.csv: sha256 mismatch")
    if bad:
        print("DATA VERIFICATION FAILED:\n  " + "\n  ".join(bad))
        sys.exit(1)
    print(f"data OK: {len(manifest['datasets'])} screening datasets + Nagtegaal, all SHA-256 verified")


if __name__ == "__main__":
    main()
