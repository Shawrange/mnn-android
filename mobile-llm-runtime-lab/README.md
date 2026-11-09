# MNN Android CPU Runtime Lab｜Gate 1

只使用固定MNN二进制/模型的CPU 4线程基线。MNN源码、编译和模型资产来自相邻`gate0/`；不在此仓复制权重，不修改上游Runtime，不测试GPU/NPU。

- 配置：`configs/cpu.json`，包括精确commit、模型revision、设备/资产路径、五负载、温度门槛及失败规则。
- 运行：`scripts/run_bench.py`，每次调用新建带UTC时间+UUID的会话目录；每个进程`-rep 1`，1个warmup+1个有效样本。
- 分析：`scripts/analyze.py`，默认只分析对应phase的最新会话，也可用`--session <目录>`明确选择；重新验证原始JSON后统计，不删除速度异常点。Pilot与正式会话分开，不自动合并不同批次。
- 指标：`metrics.md`，固定源码计时范围、单位、effective dynamic_option和内存/TTFT边界。
- 独立内存诊断：`scripts/run_memory_probe.py` + `scripts/sample_memory.sh`；不与主基线并发，不混入基线。

Windows PowerShell（Python 3.12标准库，无需pip依赖）：

```powershell
python -X utf8 scripts/test_parser.py
python -X utf8 -u scripts/run_bench.py --phase pilot --rounds 2 --cooldown 5
python -X utf8 scripts/analyze.py --phase pilot
python -X utf8 -u scripts/run_bench.py --phase baseline --rounds 10 --cooldown 15
python -X utf8 scripts/analyze.py --phase baseline
# 仅在上面测量全部结束后单独运行：
python -X utf8 -u scripts/run_memory_probe.py
```

命令示例须在本项目目录执行；默认配置使用本机的绝对路径，移动项目后先修改配置的ADB、Gate0和远端资产路径。一个设备同一时间只运行一个实验进程。

`results/`保留全部原始stdout/stderr、退出码、Benchmark JSON、运行前后状态、每条ADB命令与时刻。`analysis/`的每次分析也新建目录。失败会话不覆盖、不自动删除；分析明确统计失败，原始目录中“started”但未结束的样本也不会计为成功。

最大RSS来自Android `time -v`，含加载/调优/warmup；系统MemAvailable不是该进程RSS。PSS单独诊断，采样最大值不等于精确峰值。未测TTFT写null。新进程不代表清空OS页缓存。

成功标准是可追溯的样本和解释边界，不是得到某个固定吞吐数字或证明性能稳定。具体结果以`Gate1_性能基线报告.md`为准。
