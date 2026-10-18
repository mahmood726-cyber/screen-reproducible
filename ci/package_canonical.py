"""Archive one completed run's per-seed results as the canonical results of a protocol (maintainers).

  python ci/package_canonical.py --results <dir with screen/ asreview/ dedup.json [logs/]> --protocol v1.0.1 --mode full \
      --provenance "GitHub Actions run 123, job full-docker (Docker, ubuntu-latest), commit abc1234"

Copies the per-seed result files (screen/*.json, asreview/*.json, dedup.json, logs/*.log) into
canonical/<protocol>/<mode>/results/, writes canonical/<protocol>/<mode>/SHA256SUMS and PROVENANCE.json.
These are the "per-seed outputs" of the Extended data: they are committed to the repository (and so are in
every Zenodo release made from it), and `python reproduce.py --protocol <p> --from-canonical` rebuilds every
table, figure and the PASS/FAIL check from them without re-running the benchmark. Nothing here changes a
result; the files are copied byte for byte.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--mode", default="full")
    ap.add_argument("--provenance", required=True, help="where the run came from (CI run id, job, platform, commit)")
    a = ap.parse_args()
    src = Path(a.results)
    for need in ("screen", "asreview", "dedup.json"):
        if not (src / need).exists():
            raise SystemExit(f"{src} has no {need}: not a complete results directory")
    dst = ROOT / "canonical" / a.protocol / a.mode
    if (dst / "results").exists():
        shutil.rmtree(dst / "results")
    files = []
    for pat in ("screen/*.json", "asreview/*.json", "dedup.json", "logs/*.log"):
        for f in sorted(src.glob(pat)):
            rel = f.relative_to(src)
            out = dst / "results" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, out)
            files.append(out)
    if not any(p.parent.name == "screen" for p in files):
        raise SystemExit("no screen results copied")
    sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(dst).as_posix()}\n" for p in files)
    (dst / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    (dst / "PROVENANCE.json").write_text(json.dumps({
        "protocol": a.protocol, "mode": a.mode, "provenance": a.provenance, "files": len(files),
        "packaged": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "rebuild": f"python reproduce.py --protocol {a.protocol}{' --quick' if a.mode == 'quick' else ''} --from-canonical",
    }, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(files)} files -> {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
