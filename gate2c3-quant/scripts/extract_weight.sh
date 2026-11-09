#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2c3-quant
s=/home/shawrange/src/MNN-3.6.2
mkdir -p "$r/evidence/weight" "$r/evidence/extractor-build" "$r/staging"
cmd=(g++ -std=c++17 -O2 -I"$s/schema/current" -I"$s/3rd_party/flatbuffers/include" -I"$s/transformers/llm/engine/app/jsonhpp" "$r/scripts/extract_weight.cpp" -o "$r/staging/extract_weight")
printf '%q ' "${cmd[@]}" > "$r/evidence/extractor-build/command.txt"
set +e
"${cmd[@]}" > "$r/evidence/extractor-build/stdout.txt" 2> "$r/evidence/extractor-build/stderr.txt"
rc=$?
echo "$rc" > "$r/evidence/extractor-build/exit.txt"
set -e
[[ $rc == 0 ]]
"$r/staging/extract_weight" /mnt/e/DUANCE/gate0/assets/Qwen3-0.6B-MNN/llm.mnn /mnt/e/DUANCE/gate0/assets/Qwen3-0.6B-MNN/llm.mnn.weight "$r/evidence/weight/q"
