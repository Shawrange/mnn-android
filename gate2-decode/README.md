# Gate 2-A：Decode执行机制研究

本目录独立于Gate 1。入口报告是 `Gate2_Decode执行机制研究报告.md`，源码说明是 `调用链与源码引用.md`。不包含优化实现。

## 文件布局

- `diagnostic-design.md`：实验前协议。
- `evidence/gate1-audit/`：50个既有样本核对、10区组配对、设备状态复核、Gate1保护哈希。
- `evidence/diagnostic.patch`：独立诊断分支全部修改；基底固定commit，宏MNN_GATE2_TRACE。
- `evidence/source/{clean,diagnostic}/`：关键源码快照，行号引用使用clean。
- `evidence/build/`：Ninja构建命令、完整日志、exit、cache、ELF、二进制哈希。
- `staging/`：诊断库/官方CLI及独立功能驱动；原始Gate0文件仍保留在原目录。
- `results/`：setup、correctness、pilot、control相互分开；每次UTC+UUID，不覆盖旧结果。
- `analysis/`：汇总JSON、samples/segments/paired/growth-events CSV、设备时间线解析、图及绘图数据。

## 当前主机复现

需要Windows Python、ADB和现有WSL Linux NDK/CMake/Ninja。分析/运行使用Python标准库；可选绘图需要matplotlib。路径、serial、模型及冷却配置源自复制的Gate1配置；换主机需调整 `run_experiments.py` 的C/REMOTE/CONFIG及构建脚本中的绝对路径。不要更改原Gate1配置。

在新worktree建立诊断分支，将保存补丁应用于固定基底（现有诊断worktree已应用，不重复运行instrument.py）：

```bash
git -C /home/shawrange/src/MNN-3.6.2 worktree add -b diagnostic/decode-gate2a-reproduce /home/shawrange/src/MNN-decode-reproduce 7e3c6fb5225d3ccf22807ee641332669df34650d
git -C /home/shawrange/src/MNN-decode-reproduce apply /mnt/e/DUANCE/gate2-decode/evidence/diagnostic.patch
ANDROID_NDK=/home/shawrange/Android/android-ndk-r27c bash /mnt/e/DUANCE/gate2-decode/scripts/build_diagnostic.sh /home/shawrange/src/MNN-decode-reproduce /home/shawrange/src/MNN-decode-reproduce/build-gate2
```

构建目录必须全新。`stage_build.py`默认收集本次实际worktree/build-gate2，复现新路径时先调整其b变量。`build_correctness.sh`使用保留的干净头文件/库编译同一个外部驱动。不要替换Gate0/staging中的任何文件。

Windows项目根目录 `E:\DUANCE`：

```powershell
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2-decode/scripts/build_correctness.sh
wsl -d Ubuntu -- python3 /mnt/e/DUANCE/gate2-decode/scripts/stage_build.py
python -B gate2-decode/scripts/run_experiments.py setup
python -B gate2-decode/scripts/run_experiments.py correctness
python -B gate2-decode/scripts/run_experiments.py pilot
python -B gate2-decode/scripts/run_experiments.py control --blocks 6
python -B gate2-decode/scripts/analyze.py
python -B gate2-decode/scripts/plot_trace.py
python -B gate2-decode/scripts/write_report.py
python -B gate2-decode/scripts/validate_results.py
wsl -d Ubuntu -- python3 /mnt/e/DUANCE/gate2-decode/scripts/verify_source_snapshots.py
python -B gate2-decode/scripts/verify_evidence.py
```

分析脚本会汇总本目录全部control会话；本次只有一个。新增研究条件时建立独立项目目录或明确筛选会话，不能混池后沿用本报告结论。首次实验Gate1审计脚本已运行，不重写原保护哈希。

## 观测边界

clean/off/on分别是干净库、诊断库不设prefix、诊断库设置prefix；本次两个llm_bench文件哈希相同，变化实际在libMNN.so。每次记录显式LD_LIBRARY_PATH并验证设备产物哈希。

Trace仅支持本实验的**单LLM、单调用线程、同步普通AR执行**。固定缓冲8192步骤/8192扩容事件；溢出有dropped，验证非零即失败。它不是可并发请求的产品Tracing接口。worker由原Runtime调度，scope只包围同步parent调用，无worker TLS传播假设。每步28+28调用及KV长度核对覆盖。进程正常退出才写Trace；崩溃/超时导致缺失不能当成功。

无Tracing的clean/off运行不产生逐Token文件；on运行与warmup一起缓冲，按response=2选择有效测量。功能实验只有response=1，不能与Benchmark Trace混用。

CPU频率及进程/线程调度按约0.5秒加读取开销采样，所有控制模式使用相同observer；这是额外观测负载，未独立量化其开销，不能与Gate1绝对TPS直接合并。`/proc/uptime`与Trace的CLOCK_MONOTONIC可能存在suspend偏移，未采集同步offset，**不做token与频率/调度的精确时刻关联**。HAL温度仅前后快照，sysfs单温区另行记录，不当作逐Token CPU温度。

native Decode计时不含Token scope开始/结束本身的部分开销；开销表同时给原生JSON及包含采样等工作的wall proxy。wall proxy还含prefill计时外的工作，不能称纯Decode wall。on/off独立进程比较受设备漂移影响，小样本范围不能给出精确零开销保证。

原始失败完整保留且停止后续采样；不会按速度剔除。timeout后不自动重试，不保证远端已杀掉子进程，排查完残留进程后才能再次实验。
