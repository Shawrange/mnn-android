#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2c3-quant
mkdir -p "$r/evidence/reference-build"
cmd=(g++ -std=c++17 -O2 -ffp-contract=off "$r/scripts/reference.cpp" -o "$r/staging/reference")
printf '%q ' "${cmd[@]}" > "$r/evidence/reference-build/command.txt"
set +e
"${cmd[@]}" > "$r/evidence/reference-build/stdout.txt" 2> "$r/evidence/reference-build/stderr.txt"
rc=$?
echo "$rc" > "$r/evidence/reference-build/exit.txt"
exit "$rc"
