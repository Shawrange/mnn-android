#!/usr/bin/env bash
set -euo pipefail
root=/mnt/e/DUANCE/gate2-decode
ndk=/home/shawrange/Android/android-ndk-r27c
src=/home/shawrange/src/MNN-3.6.2
cmd=("$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++" -std=c++17 -O3 -fno-exceptions -fno-rtti -static-libstdc++
 -I"$src/include" -I"$src/transformers/llm/engine/include" "$root/scripts/correctness.cpp"
 -L"$src/build-android-arm64-cpu-gate0" -lMNN -Wl,-z,max-page-size=16384 -o "$root/staging/correctness")
printf '%q ' "${cmd[@]}" > "$root/evidence/build/correctness.command.txt"
printf '\n' >> "$root/evidence/build/correctness.command.txt"
set +e
"${cmd[@]}" > "$root/evidence/build/correctness.build.log" 2>&1
code=$?
set -e
printf '%s\n' "$code" > "$root/evidence/build/correctness.exit.txt"
exit "$code"
