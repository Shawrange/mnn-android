#!/usr/bin/env bash
set -euo pipefail
evidence=/mnt/e/DUANCE/gate0/evidence/source-checkout
mkdir -p "$evidence"
if [[ -f "$evidence/checkout.log" ]]; then
  cp "$evidence/checkout.log" "$evidence/checkout-prior-attempt.log"
  cp "$evidence/checkout.exit.txt" "$evidence/checkout-prior-attempt.exit.txt" 2>/dev/null || true
fi
exec > >(tee "$evidence/checkout.log") 2>&1
trap 'code=$?; printf "%s\n" "$code" > "$evidence/checkout.exit.txt"' EXIT
expected=7e3c6fb5225d3ccf22807ee641332669df34650d
source_dir="$HOME/src/MNN-3.6.2"
mkdir -p "$HOME/src"
if [[ ! -e "$source_dir" ]]; then
  if [[ $# -eq 1 ]]; then
    git -c core.autocrlf=false clone --no-hardlinks "$1" "$source_dir"
    git -C "$source_dir" remote set-url origin https://github.com/alibaba/MNN.git
  else
    git -c core.autocrlf=false clone --depth 1 --branch 3.6.2 https://github.com/alibaba/MNN.git "$source_dir"
  fi
fi
test -d "$source_dir/.git"
test "$(git -C "$source_dir" rev-parse HEAD)" = "$expected"
test "$(git -C "$source_dir" rev-parse '3.6.2^{commit}')" = "$expected"
test -z "$(git -C "$source_dir" status --porcelain --untracked-files=no)"
git -C "$source_dir" fsck --no-reflogs
git -C "$source_dir" show -s --format=fuller HEAD
git -C "$source_dir" remote -v
git -C "$source_dir" ls-tree -r HEAD | wc -l
git -C "$source_dir" status --short > "$evidence/git-status.txt"
git -C "$source_dir" rev-parse HEAD > "$evidence/commit.txt"
printf '%s\n' "$source_dir" > "$evidence/source-path.txt"
find "$source_dir" -name AGENTS.md -print > "$evidence/agents-files.txt"
printf 'Full working tree at pinned commit verified: %s\n' "$source_dir"
