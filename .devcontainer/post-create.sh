#!/usr/bin/env bash
# Runs once when the Codespace (or local dev container) is created: the pinned environment is already
# installed by the Dockerfile, so this fetches the SHA-256-checked datasets and runs the quick reproduction
# under both benchmark protocols (v1.0.0 = the paper's protocol, v1.0.1 = the corrected default).
set -uo pipefail
cd "$(dirname "$0")/.."
echo
echo "== screen-reproducible: quick reproduction (4 small datasets, 1 seed), protocols v1.0.0 and v1.0.1 =="
rc=0
python bench/fetch_data.py || rc=$?
for p in v1.0.0 v1.0.1; do
  if [ $rc -eq 0 ]; then python reproduce.py --quick --protocol $p || rc=$?; fi
done
echo
if [ $rc -eq 0 ]; then echo "QUICK RUN: ALL PASS  (reports: outputs/v1.0.0/quick/ and outputs/v1.0.1/quick/reproduction_report.md)"; else echo "QUICK RUN FAILED (exit $rc); see the output above and outputs/<protocol>/quick/reproduction_report.md"; fi
cat <<'EOF'

Next:
  python reproduce.py --protocol v1.0.0   # full run: every number printed in the paper (uses every core)
  python reproduce.py                     # full run, protocol v1.0.1 (the corrected default)
  results land in outputs/<protocol>/full/  (reproduction_report.md = expected vs reproduced, PASS/FAIL per number)
  the app itself: open app/screen/index.html (or the live app linked in README.md)
EOF
exit $rc
