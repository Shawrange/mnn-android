#!/usr/bin/env bash
set -euo pipefail
root=/mnt/e/DUANCE/gate2b-decode-hotspots
src=/home/shawrange/src/MNN-3.6.2
mkdir -p "$root/evidence/model"
set +e
g++ -O2 -std=c++17 -I"$src/schema/current" -I"$src/3rd_party/flatbuffers/include" "$root/scripts/inspect_graph.cpp" -o "$root/staging/inspect_graph_host" > "$root/evidence/model/compile.stdout.txt" 2> "$root/evidence/model/compile.stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$root/evidence/model/compile.exit.txt"
if [[ $rc != 0 ]]; then exit "$rc"; fi
"$root/staging/inspect_graph_host" /mnt/e/DUANCE/gate0/assets/Qwen3-0.6B-MNN/llm.mnn > "$root/evidence/model/graph-detailed.tsv" 2> "$root/evidence/model/inspect.stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$root/evidence/model/inspect.exit.txt"
exit "$rc"
