#!/usr/bin/env bash
set -euo pipefail
root=/mnt/e/DUANCE/gate2b-decode-hotspots
src=/home/shawrange/src/MNN-3.6.2
mkdir -p "$root/evidence/build"
cmd=(/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++
 -std=c++17 -O3 -fno-exceptions -fno-rtti -static-libstdc++ -I"$src/include" -I"$src/transformers/llm/engine/include"
 "$root/scripts/op_probe.cpp" -L"$src/build-android-arm64-cpu-gate0" -lMNN -Wl,-z,max-page-size=16384 -o "$root/staging/op_probe")
printf '%q ' "${cmd[@]}" > "$root/evidence/build/probe.command.txt"
set +e
"${cmd[@]}" > "$root/evidence/build/probe.stdout.txt" 2> "$root/evidence/build/probe.stderr.txt"
rc=$?
set -e
printf '%s\n' "$rc" > "$root/evidence/build/probe.exit.txt"
sha256sum "$root/staging/op_probe" > "$root/evidence/build/probe.sha256"
exit "$rc"
