#!/usr/bin/env bash
# Gate2-C: clean pinned OpenCL build, no source edits.
set -euo pipefail
expected_commit=7e3c6fb5225d3ccf22807ee641332669df34650d
if [[ $# -lt 1 || $# -gt 2 ]]; then
  printf 'Usage: ANDROID_NDK=/path/to/linux-ndk bash %s /path/to/MNN [new-build-directory]\n' "$0" >&2
  exit 2
fi
source_dir=$(realpath "$1")
build_dir=${2:-"$source_dir/build-android-arm64-opencl-gate2c"}
: "${ANDROID_NDK:?Set ANDROID_NDK to a Linux x86_64 NDK installation}"
for tool in git cmake ninja; do command -v "$tool" >/dev/null; done
test -f "$ANDROID_NDK/build/cmake/android.toolchain.cmake"
test -x "$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
actual_commit=$(git -C "$source_dir" rev-parse HEAD)
if [[ "$actual_commit" != "$expected_commit" ]]; then
  printf 'Wrong MNN commit: %s (expected %s)\n' "$actual_commit" "$expected_commit" >&2
  exit 2
fi
if [[ -n $(git -C "$source_dir" status --porcelain --untracked-files=no) ]]; then
  printf 'Tracked source changes exist; use a clean pinned checkout.\n' >&2
  exit 2
fi
if [[ -e "$build_dir/CMakeCache.txt" ]]; then
  printf 'Use a new build directory to avoid stale backend/toolchain settings: %s\n' "$build_dir" >&2
  exit 2
fi
mkdir -p "$build_dir"
run_logged() {
  local label=$1
  shift
  printf '%q ' "$@" > "$build_dir/$label.command.txt"
  printf '\n' >> "$build_dir/$label.command.txt"
  set +e
  "$@" 2>&1 | tee "$build_dir/$label.log"
  local codes=("${PIPESTATUS[@]}")
  set -e
  printf '%s\n' "${codes[0]}" > "$build_dir/$label.exit.txt"
  if [[ ${codes[0]} -ne 0 ]]; then return "${codes[0]}"; fi
  return "${codes[1]}"
}
{
  date -u '+%Y-%m-%dT%H:%M:%SZ'
  printf 'mnn_commit=%s\n' "$actual_commit"
  cat "$ANDROID_NDK/source.properties"
  cmake --version
  ninja --version
  "$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++" --version
} > "$build_dir/build-environment.txt"
run_logged configure cmake -S "$source_dir" -B "$build_dir" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK/build/cmake/android.toolchain.cmake" \
  -DCMAKE_CXX_FLAGS=-DOPENCL_FALLBACK_LOG -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=17 \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-21 \
  -DANDROID_STL=c++_static \
  -DCMAKE_SHARED_LINKER_FLAGS='-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384' \
  -DCMAKE_EXE_LINKER_FLAGS='-Wl,-z,max-page-size=16384 -Wl,-z,common-page-size=16384' \
  -DMNN_BUILD_FOR_ANDROID_COMMAND=ON -DMNN_USE_LOGCAT=OFF \
  -DMNN_BUILD_SHARED_LIBS=ON -DMNN_SEP_BUILD=OFF \
  -DMNN_BUILD_LLM=ON -DMNN_LLM_BUILD_DEMO=ON \
  -DMNN_LOW_MEMORY=ON -DMNN_SUPPORT_TRANSFORMER_FUSE=ON \
  -DMNN_ARM82=ON -DMNN_SME2=OFF -DMNN_KLEIDIAI=OFF \
  -DMNN_USE_SSE=OFF -DMNN_OPENMP=OFF -DMNN_USE_THREAD_POOL=ON \
  -DMNN_OPENCL=ON -DMNN_OPENCL_SIZE_CUT=OFF -DMNN_GPU_TIME_PROFILE=ON -DMNN_OPENGL=OFF -DMNN_VULKAN=OFF -DMNN_CUDA=OFF \
  -DMNN_QNN=OFF -DMNN_HEXAGON=OFF -DMNN_NNAPI=OFF -DMNN_NPU=OFF \
  -DMNN_BUILD_LLM_OMNI=OFF -DMNN_BUILD_DIFFUSION=OFF \
  -DMNN_BUILD_OPENCV=OFF -DMNN_BUILD_AUDIO=OFF -DMNN_IMGCODECS=OFF \
  -DMNN_BUILD_TEST=OFF -DMNN_LLM_BUILD_TEST=OFF -DMNN_BUILD_BENCHMARK=OFF \
  -DMNN_BUILD_TOOLS=OFF -DMNN_BUILD_CONVERTER=OFF -DMNN_BUILD_TRAIN=OFF \
  -DMNN_LLM_TOKEN_COMPRESS=OFF -DLLM_SUPPORT_HTTP_RESOURCE=OFF -DBUILD_MLS=OFF
run_logged build cmake --build "$build_dir" --target llm_demo llm_bench --parallel 4
cmake -LA -N "$build_dir" > "$build_dir/cmake-cache-summary.txt"
readelf_tool="$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
for artifact in llm_demo llm_bench libMNN.so; do
  test -s "$build_dir/$artifact"
  "$readelf_tool" -h -l -d "$build_dir/$artifact" > "$build_dir/$artifact.readelf.txt"
done
(cd "$build_dir" && sha256sum llm_demo llm_bench libMNN.so > binaries.sha256)
printf 'Build artifacts produced; Android runtime verification remains separate: %s\n' "$build_dir"
