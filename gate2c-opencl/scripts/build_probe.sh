#!/usr/bin/env bash
set -euo pipefail
root=/mnt/e/DUANCE/gate2c-opencl
mkdir -p "$root/evidence/probe-build"
cmd=(/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android21-clang++ -std=c++17 -O2 -static-libstdc++ -I/home/shawrange/src/MNN-3.6.2/3rd_party/OpenCLHeaders "$root/scripts/cl_probe.cpp" -ldl -o "$root/staging/cl_probe")
printf '%q ' "${cmd[@]}" > "$root/evidence/probe-build/command.txt"
set +e
"${cmd[@]}" > "$root/evidence/probe-build/stdout.txt" 2> "$root/evidence/probe-build/stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$root/evidence/probe-build/exit.txt"
exit "$rc"
