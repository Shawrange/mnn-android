#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cat /mnt/e/DUANCE/gate0/evidence/source-checkout/source-path.txt)
build_dir="$source_dir/build-android-arm64-cpu-gate0"
evidence=/mnt/e/DUANCE/gate0/evidence/build
file "$build_dir/llm_demo" "$build_dir/llm_bench" "$build_dir/libMNN.so" | tee "$evidence/file-types.txt"
cp "$build_dir/CMakeFiles/4.2.3/CMakeCXXCompiler.cmake" "$evidence/CMakeCXXCompiler.cmake"
ninja -C "$build_dir" -t commands > "$evidence/ninja-commands.txt"
git -C "$source_dir" status --short --untracked-files=no
