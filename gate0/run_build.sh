#!/usr/bin/env bash
set -euo pipefail
evidence=/mnt/e/DUANCE/gate0/evidence/build
mkdir -p "$evidence"
exec > >(tee "$evidence/build-stage.log") 2>&1
trap 'code=$?; printf "%s\n" "$code" > "$evidence/build-stage.exit.txt"' EXIT
export ANDROID_NDK
ANDROID_NDK=$(cat /mnt/e/DUANCE/gate0/evidence/installation/ndk-path.txt)
source_dir=$(cat /mnt/e/DUANCE/gate0/evidence/source-checkout/source-path.txt)
bash /mnt/e/DUANCE/gate0/build_android_cpu.sh "$source_dir"
build_dir="$source_dir/build-android-arm64-cpu-gate0"
for name in configure.log build.log configure.exit.txt build.exit.txt configure.command.txt build.command.txt build-environment.txt cmake-cache-summary.txt CMakeCache.txt binaries.sha256 llm_demo.readelf.txt llm_bench.readelf.txt libMNN.so.readelf.txt; do
  cp "$build_dir/$name" "$evidence/$name"
done
mkdir -p /mnt/e/DUANCE/gate0/staging
cp "$build_dir/llm_demo" "$build_dir/llm_bench" "$build_dir/libMNN.so" /mnt/e/DUANCE/gate0/staging/
git -C "$source_dir" diff --exit-code
git -C "$source_dir" diff --cached --exit-code
git -C "$source_dir" status --short --untracked-files=no > "$evidence/final-tracked-status.txt"
