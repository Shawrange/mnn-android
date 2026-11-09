#!/system/bin/sh
while kill -0 "$1" 2>/dev/null; do
 printf '@@CLOCK '; LD_LIBRARY_PATH=. ./op_probe --clock
 for p in /sys/devices/system/cpu/cpufreq/policy*; do
  printf '%s ' "${p##*/}"
  cat "$p/scaling_cur_freq" "$p/scaling_max_freq"
 done
 for pid in $(pidof llm_bench op_probe); do
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
