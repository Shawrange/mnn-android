#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2c3-quant
s=/home/shawrange/src/MNN-3.6.2
mkdir -p "$r/evidence/replay-build"
cmd=(/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++ -std=c++17 -O2 -static-libstdc++ -I"$s/include" -I"$s/source" -I"$s/schema/current" -I"$s/3rd_party/flatbuffers/include" -I"$s/transformers/llm/engine/app/jsonhpp" "$r/scripts/replay.cpp" -L"$s/build-android-arm64-cpu-gate0" -lMNN -o "$r/staging/replay")
printf '%q ' "${cmd[@]}" > "$r/evidence/replay-build/command.txt"
set +e
"${cmd[@]}" > "$r/evidence/replay-build/stdout.txt" 2> "$r/evidence/replay-build/stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$r/evidence/replay-build/exit.txt"
exit "$rc"
