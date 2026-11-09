# Gate2-C4 模型质量验收

[主报告](Gate2C4_模型质量验收报告.md)｜[冻结协议](protocol.md)｜[冻结哈希](freeze.json)｜[源码与推理边界](源码与推理边界.md)｜[核验](verification-summary.json)

结论C：CPU24/100、GPU25/100，固定实验组未达到预定应用质量，不进入GPU性能基线。没有修改模型或Runtime，没有优化/NPU实验，旧Logits门槛及失败保留。

## 交付索引

- `datasets/pilot.jsonl`：12条独立试跑；`formal.jsonl`：冻结100条（每类25），唯一ID/输入/gold/变体/评分/参考答案齐全。
- `freeze.json`：正式前冻结的协议、数据、评分器/测试、运行配置/驱动/可执行文件哈希与时间；禁止重写。
- `scripts/score.py`、`test_score.py`：确定性评分及10个正反例测试；`evidence/scorer-tests.*`为冻结前实际测试记录。
- `results/formal-*`：正式200次独立进程，完整原始文本/Token IDs/模板/有效配置/日志/退出码/评分，每20进程设备状态；`schedule.json`预定顺序。
- `results/pilot-*`：试跑24次；不计正式样本。
- `results/gpu-evidence-*`：独立profile哨兵，真实事件与回退诊断；不混入clean质量或性能统计。
- `results/diagnostics-*`：6例×2前缀位置×2后端的原始完整Logits；前三例两个位置语义重复，分析有说明。另含3条任务discordance每后端2次复跑，不新增正式case。
- `analysis/paired-quality.json`、`paired-cases.csv`：全部100例配对、各任务成功率/区间、失败原因、原始文本。
- `analysis/logits-selection.json`、`logits-diagnostics.json`：固定选择规则、同历史核验、Top5/margin/概率/rank、原Decode重放不一致和参考Token适用边界。
- `analysis/review-records.json`：代理对代表性客观评分的审查记录，不冒称独立人类复核、不改主分。
- `analysis/gpu-execution-evidence.json`、`decision.json`：GPU落点证据及最终决策。
- `evidence/source/`：11个固定commit源码快照和manifest；`environment`：主机、设备及所有部署库/工具/配置最终哈希。
- `evidence/prior-hashes.json`：开始时9665个前期文件的保护哈希，不覆盖。
- `artifact-manifest.sha256.json`：本交付文件哈希；与verification-summary分项核对。

所有文本UTF8；`logits.f32`为小端无头float32，shape `[1,1,151936]`。output_ids含自然stop151645，text为生成器原始非stop文本。不能删除代码围栏/标点后当作本组成功。

## 复现和只读分析

Windows工作目录`E:\DUANCE`，既有WSL Ubuntu/Linux NDK r27c、Python标准库及Windows ADB serial ee19377b。固定模型路径/库在脚本中明确；换机器先修改**新实验副本**，不要改本已冻结组。

只读重算当前结果：

```powershell
python -B gate2c4-quality/scripts/test_score.py
python -B gate2c4-quality/scripts/analyze.py
python -B gate2c4-quality/scripts/analyze_diagnostics.py
python -B gate2c4-quality/scripts/finalize_analysis.py
python -B gate2c4-quality/scripts/write_report.py
python -B gate2c4-quality/scripts/verify.py
```

真机复现（同冻结组新UUID目录，不覆盖旧结果；会额外运行实验）：

```powershell
python -B gate2c4-quality/scripts/run.py formal
python -B gate2c4-quality/scripts/analyze.py
python -B gate2c4-quality/scripts/run.py gpu-evidence
python -B gate2c4-quality/scripts/run_diagnostics.py
```

`analyze.py`选择最新completed正式会话，诊断选最新completed对应会话；审查其他会话时必须显式核对配对，不可新增数据后沿用旧统计。运行失败仍保存score/result和分母，不静默删除；超时后先检查远端进程结束，不叠加重试。

现有可执行文件的SHA256已冻结；**不要重新编译覆盖后仍声称freeze未变**。`build_probe.sh`仅供检查构建步骤；要改驱动/配置/评分，复制新项目并创建新冻结。`make_pilot.py`、`make_formal.py`、`freeze.py`为一次性建立过程，已有文件拒绝覆盖。`prepare.py`不再运行。

本轮已按C结束。若后续更换模型、打开Thinking、改变后处理/提示或放宽格式，应作为独立质量实验重新设计，不回改本轮结果，也不自动启动GPU性能基线。
