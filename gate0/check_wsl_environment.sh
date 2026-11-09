#!/usr/bin/env bash
set -u
cat /etc/os-release
uname -m
printf '\nPATH=%s\n' "$PATH"
for tool in git cmake ninja make clang clang++ g++ python3 adb java unzip curl file; do
  printf '\n[%s]\n' "$tool"
  if command -v "$tool"; then "$tool" --version 2>&1 | head -n 2; else printf 'NOT_FOUND\n'; fi
done
printf '\nANDROID_HOME=%s\nANDROID_NDK=%s\nANDROID_NDK_HOME=%s\n' "${ANDROID_HOME:-}" "${ANDROID_NDK:-}" "${ANDROID_NDK_HOME:-}"
for root in "$HOME/Android/Sdk" "$HOME/android-sdk" /opt/android-sdk /opt/android-ndk /usr/lib/android-sdk; do
  if test -d "$root"; then ls -ld "$root"; find "$root" -maxdepth 4 -name source.properties -o -name android.toolchain.cmake; fi
done
