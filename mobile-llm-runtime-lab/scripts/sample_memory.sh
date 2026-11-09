#!/system/bin/sh
# Separate diagnostic run: polling overhead excludes these runs from the baseline.
base=$1
pp=$2
tg=$3
dest=$4
mkdir -p "$dest" || exit 2
cd "$base" || exit 2
LD_LIBRARY_PATH=. ./llm_bench -m Qwen3-0.6B-MNN/config.cpu.json \
 -a cpu -t 4 -p 0 -n 0 -pg "$pp,$tg" -rep 1 -c 2 \
 --memory 2 --power 0 -dyo 0 -mmp 0 -qa 0 -fa 1 -load false \
 -j "$dest/benchmark.json" > "$dest/benchmark.stdout.txt" 2> "$dest/benchmark.stderr.txt" &
child=$!
printf '%s\n' "$child" > "$dest/pid.txt"
while kill -0 "$child" 2>/dev/null; do
  echo "@@SAMPLE $(date +%s) $(cat /proc/uptime)" >> "$dest/memory.txt"
  grep -E '^Name:|^Pid:|^VmRSS:|^VmHWM:|^VmSwap:' "/proc/$child/status" >> "$dest/memory.txt" 2>> "$dest/memory-errors.txt"
  echo "status_exit=$?" >> "$dest/memory.txt"
  cat "/proc/$child/smaps_rollup" >> "$dest/memory.txt" 2>> "$dest/memory-errors.txt"
  echo "smaps_exit=$?" >> "$dest/memory.txt"
  sleep 0.5
done
wait "$child"
code=$?
printf '%s\n' "$code" > "$dest/benchmark.exit.txt"
exit "$code"
