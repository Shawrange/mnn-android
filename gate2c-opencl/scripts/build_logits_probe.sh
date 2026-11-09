#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2c-opencl
s=/home/shawrange/src/MNN-3.6.2
mkdir -p "$r/evidence/logits-probe-build"
cmd=(/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++ -std=c++17 -O2 -static-libstdc++ -I"$s/include" -I"$s/transformers/llm/engine/include" "$r/scripts/logits_probe.cpp" -L"$s/build-android-arm64-cpu-gate0" -lMNN -o "$r/staging/logits_probe")
printf '%q ' "${cmd[@]}" > "$r/evidence/logits-probe-build/command.txt"
set +e
"${cmd[@]}" > "$r/evidence/logits-probe-build/stdout.txt" 2> "$r/evidence/logits-probe-build/stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$r/evidence/logits-probe-build/exit.txt"
exit "$rc"
