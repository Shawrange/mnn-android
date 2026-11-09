#!/usr/bin/env bash
set -euo pipefail
r=/mnt/e/DUANCE/gate2d-comparison
s=/home/shawrange/src/MNN-3.6.2
mkdir "$r/evidence/count-probe-build"
cmd=(/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++ -std=c++17 -O2 -static-libstdc++ -I"$s/include" -I"$s/transformers/llm/engine/include" -I"$s/transformers/llm/engine/app/jsonhpp" "$r/scripts/count_probe.cpp" -L"$s/build-android-arm64-cpu-gate0" -lMNN -o "$r/staging/count_probe")
printf '%q ' "${cmd[@]}" > "$r/evidence/count-probe-build/command.txt"
set +e
"${cmd[@]}" > "$r/evidence/count-probe-build/stdout.txt" 2> "$r/evidence/count-probe-build/stderr.txt"
rc=$?
echo "$rc" > "$r/evidence/count-probe-build/exit.txt"
exit "$rc"
