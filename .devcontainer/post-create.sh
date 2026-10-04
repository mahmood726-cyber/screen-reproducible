#!/usr/bin/env bash
# Runs once when the Codespace (or local dev container) is created: the pinned environment is already
# installed by the Dockerfile, so this fetches the SHA-256-checked datasets and runs the quick reproduction.
set -uo pipefail
cd "$(dirname "$0")/.."
echo
echo "== screen-reproducible: quick reproduction (4 small datasets, 1 seed; under a minute) =="
python bench/fetch_data.py && python reproduce.py --quick
rc=$?
echo
if [ $rc -eq 0 ]; then echo "QUICK RUN: ALL PASS  (report: outputs/quick/reproduction_report.md)"; else echo "QUICK RUN FAILED (exit $rc); see the output above and outputs/quick/reproduction_report.md"; fi
cat <<'EOF'

Next:
  python reproduce.py            # full run: every number in the paper (about 30-80 min, uses every core)
  results land in outputs/full/  (reproduction_report.md = expected vs reproduced, PASS/FAIL per number)
  the app itself: open app/screen/index.html (or the live app linked in README.md)
EOF
exit $rc
