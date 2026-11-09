#!/system/bin/sh
# One sample per 0.5s, same observer in clean/off/on. No root.
while kill -0 "$1" 2>/dev/null; do
 echo "@@TICK $(cat /proc/uptime)"
 for p in /sys/devices/system/cpu/cpufreq/policy*; do
  printf '%s ' "${p##*/}"
  cat "$p/scaling_cur_freq" "$p/scaling_max_freq"
 done
 for pid in $(pidof llm_bench); do
  echo "@@PID $pid"
  cat /proc/$pid/stat
  for task in /proc/$pid/task/*; do
   echo "@@TASK ${task##*/}"
   cat "$task/schedstat"
   grep -E 'voluntary_ctxt_switches|nonvoluntary_ctxt_switches' "$task/status"
  done
 done
 sleep 0.5
done
