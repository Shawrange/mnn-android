#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2c2-numerics
s=/home/shawrange/src/MNN-3.6.2
mkdir -p "$r/evidence/probe-build" "$r/staging"
cmd=(/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++ -std=c++17 -O2 -static-libstdc++ -I"$s/include" -I"$s/source" -I"$s/schema/current" -I"$s/3rd_party/flatbuffers/include" -I"$s/transformers/llm/engine/include" -I"$s/transformers/llm/engine/app/jsonhpp" "$r/scripts/numeric_probe.cpp" -L"$s/build-android-arm64-cpu-gate0" -lMNN -o "$r/staging/numeric_probe")
printf '%q ' "${cmd[@]}" > "$r/evidence/probe-build/command.txt"
set +e
"${cmd[@]}" > "$r/evidence/probe-build/stdout.txt" 2> "$r/evidence/probe-build/stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$r/evidence/probe-build/exit.txt"
exit "$rc"
