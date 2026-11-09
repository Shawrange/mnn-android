#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2c-opencl
s=/home/shawrange/src/MNN-3.6.2
mkdir -p "$r/evidence/npu-static"
cmd=(g++ -O2 -std=c++17 -I"$s/schema/current" -I"$s/3rd_party/flatbuffers/include" "$r/scripts/inspect_npu_model.cpp" -o "$r/staging/inspect_npu_model_host")
printf '%q ' "${cmd[@]}" > "$r/evidence/npu-static/compile.command.txt"
set +e
"${cmd[@]}" > "$r/evidence/npu-static/compile.stdout.txt" 2> "$r/evidence/npu-static/compile.stderr.txt"
rc=$?;printf '%s\n' "$rc" > "$r/evidence/npu-static/compile.exit.txt"
if [[ $rc != 0 ]]; then exit "$rc"; fi
"$r/staging/inspect_npu_model_host" /mnt/e/DUANCE/gate0/assets/Qwen3-0.6B-MNN/llm.mnn > "$r/evidence/npu-static/model-properties.tsv" 2> "$r/evidence/npu-static/inspect.stderr.txt"
rc=$?;printf '%s\n' "$rc" > "$r/evidence/npu-static/inspect.exit.txt"
exit "$rc"
