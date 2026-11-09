# Gate2-C2 数值差异定位交付

入口：[报告](Gate2C2_CPU_GPU数值差异定位报告.md)、[源码与方法核查](源码与方法核查.md)、[实验协议](protocol.md)、[完整性与功能核验](verification-summary.json)。结论：第一层投影计算路径已定位；未确认Backend实现Bug，原Logits探索性门禁仍失败，不进入性能优化。

## 证据索引

- `evidence/prior-hashes.json`：前期6318文件保护清单，严禁重新覆盖。
- `evidence/source/`：38份固定源码及SHA256 manifest；source-state记录commit和tracked clean。
- `evidence/probe-build`、`replay-build*`：独立工具编译命令、日志与退出码，含最初失败。
- `evidence/environment`：手机/WSL工具链信息、状态、9个历史会话手机端库和工具哈希。
- `results/pilot-*`：CPU/GPU Low synthetic检查点小试。
- `results/low-*`：两个输入、两后端、两个进程，每次预热后重复2次完整Prefill。
- `results/high-*`：High对照（每输入/后端1进程，预热后2次）；未声明High跨进程重复性。
- `results/checkpoints-*`：两输入/两precision/两后端，11个少量检查点，Host canonical NCHW f32。
- `results/replay-*`：原图第一Q投影的工具试错和最终配对。主会话由`analysis/replay.json`明确指定，早期失败/排除版本保留；每会话有当时源代码和从手机拉回的实际工具二进制。
- 每进程`out`包含完整float32 LE Logits/检查点、meta、IDs、config；run stdout/stderr/exit与设备前后状态均保留。`.f32`为无头原始数据，shape以meta为准。
- `analysis/metrics.json`：完整模型Logits/检查点所有比较，含Top5与margin；CSV方便核查。
- `analysis/replay.json`：同输入子路径误差、重复性、入口校验、原会话排除与首次before读数异常。
- `artifact-manifest.sha256.json`：本交付产物清单；delivery完整性通过不等于Logits门禁通过。

## 当前机器复现

Windows PowerShell工作目录`E:\DUANCE`；只需Python标准库、已有ADB及WSL/NDK。脚本固定了本机源码/NDK、serial及原模型路径；换机先改新项目副本，不改旧资产。所有真机运行新建UTC+UUID会话，不覆盖历史。

```powershell
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c2-numerics/scripts/build_probe.sh
python -B gate2c2-numerics/scripts/run.py pilot
python -B gate2c2-numerics/scripts/run.py low
python -B gate2c2-numerics/scripts/run.py high
python -B gate2c2-numerics/scripts/run.py checkpoints
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c2-numerics/scripts/build_replay.sh
python -B gate2c2-numerics/scripts/run_replay.py
python -B gate2c2-numerics/scripts/analyze.py
python -B gate2c2-numerics/scripts/analyze_replay.py
python -B gate2c2-numerics/scripts/write_report.py
python -B gate2c2-numerics/scripts/verify.py
```

`analyze.py`将所有有效完整模型会话记录，不将重复进程当独立输入。`analyze_replay.py`显式选择最新已完成主会话，再强制验证r1/r2实际入口与源逐字节一致；其他会话明确排除。重新采集后不要沿用旧报告统计；先明确主会话/分组再分析、重写报告。超时/失败后检查手机进程已结束，再重试，不能叠加运行。

`prepare.py`为一次性保护快照工具，不再执行。`collect_source.py`在WSL进行固定git show比对；`capture_environment.py`在全部实验后保存环境和各会话实际设备产物。二者已真实执行，本轮未下载任何模型/SDK/依赖。重新构建可能覆盖本项目当前工具，所以历史版本已由各会话executable-evidence单独保存；正式CPU/GPU库和旧证据保持只读。

探索性阈值保持C1原值，未用新增结果回调阈值。CPU Memory_High仅是单投影辅助计算参照，不是替换模型/基线，不是性能调优。进一步研究建议与未解释边界在报告第7–8节。
