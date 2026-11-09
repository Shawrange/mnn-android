# Gate 2-B Decode热点归因

入口：[研究报告](Gate2B_Decode热点归因报告.md)、[方法与源码映射](Profiling方法与源码映射.md)、[候选与决策](工程候选与下一阶段决策.md)。本目录与前三阶段独立；上游及Gate2-A分支均未修改。

## 产物布局

- `protocol.md`：预定工作负载、冷却、样本和计时策略，以及正式采样前两次工具验证修订。
- `evidence/prior-stage-hashes.json`：Gate0/Gate1/Gate2-A原文件保护快照。
- `evidence/source/`：固定提交的31份只读源码快照与哈希。
- `evidence/model/graph-detailed.tsv`：真实图的节点、量化、维度和输入输出索引；旧graph.tsv也保留。
- `evidence/build/`：独立probe的编译命令/日志/exit/哈希；v1子目录保存溢出诊断的原源码、二进制与构建记录。
- `results/setup-*`：设备/资产哈希/help/simpleperf可用性；没有改系统设置。
- `results/correctness-*`：两个失败验证会话完整保留，最终完整功能对照成功会话单独保存。
- `results/pilot-*`：官方profile两次试跑，不与正式池混合。
- `results/official-*`：24个独立进程，6区组；off/profile各负载各6次。
- `results/detail-*`：8个独立进程，2区组；off/detail各负载各2次。
- `analysis/`：每次进程、命名算子、语义类别、残差、逐调用/逐节点分布、分段、开销配对和设备状态解析；原Trace仍在results。
- `verification-summary.json`、`artifact-manifest.sha256.json`：完整性核对与全产物哈希。

## 当前环境复现

固定MNN/model/NDK与原项目一致；脚本含当前主机的绝对路径和serial，迁移主机前调整新目录脚本，**不要改旧Gate1配置**。Windows Python标准库负责ADB及分析；matplotlib仅用于可选绘图。WSL使用既有Linux NDK、g++，模型图工具只读FlatBuffer，不访问权重数值。

当前根目录 `E:\DUANCE`：

```powershell
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2b-decode-hotspots/scripts/build_probe.sh
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2b-decode-hotspots/scripts/inspect_graph.sh
python -B gate2b-decode-hotspots/scripts/run.py setup
python -B gate2b-decode-hotspots/scripts/run.py correctness
python -B gate2b-decode-hotspots/scripts/run.py pilot
python -B gate2b-decode-hotspots/scripts/run.py official
python -B gate2b-decode-hotspots/scripts/run.py detail
python -B gate2b-decode-hotspots/scripts/analyze.py
python -B gate2b-decode-hotspots/scripts/plot.py
python -B gate2b-decode-hotspots/scripts/write_report.py
python -B gate2b-decode-hotspots/scripts/verify.py
```

每次运行使用UTC+UUID新目录，不覆盖已有实验。首次失败即停止；若timeout，须确认远端无残留进程再继续，工具不自动重试失败样本。复现研究时使用新的独立目录或明确筛选会话；本次分析器汇总所有official/detail会话、验证器固定本次计数，不能新增条件后直接混池并沿用报告。

原始stdout中的 `PROF`是官方数据；profile.json和analysis CSV均为派生文件。`name=*`是类型总计，不是另一个节点。`op_probe`只扩展观测能力、固定缓冲、进程结束写文件，不修改Runtime；off/detail完整Token/文本/状态对照一致。单调用P95仅描述同一诊断进程的调用，不是用户延迟SLA。

`freeze_evidence.py`为本次实验之前的快照，**不得重新运行覆盖保护基准**。最终verify重新比较3,915个旧文件；读取旧文件不会向旧目录写日志/缓存。
