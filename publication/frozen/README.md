# MNN Android端侧LLM Runtime执行机制研究

**已完成并冻结。** 在真实Android手机上搭建可复现的CPU/OpenCL推理链路，解释Decode成本和跨后端量化差异，并用冻结任务集检验模型质量。最终没有证据支持必须修改Runtime；固定模型的应用质量未达标，因此只完成有限硬件执行成本比较，不宣称产品可用或优化收益。

## 目标与实际平台

面向端侧推理研发岗位，研究MNN C++ Runtime、CPU Backend、移动GPU执行及工程验证方法。MNN 3.6.2，commit `7e3c6fb5225d3ccf22807ee641332669df34650d`；Qwen3-0.6B-MNN revision `34dfccda1187ded6e07ea06426da576b0b793c6b`。小米15（Snapdragon 8 Elite / Adreno830 / Android16），Windows + WSL2 Ubuntu + Linux NDK r27c / Clang18 / CMake / Ninja / ADB。桌面RTX4060Ti未承担本项目推理实验。

## 关键工程结果

- 从固定源码构建Android ARM64 Release，归档Linux NDK/Ninja命令、ELF依赖、模型LFS/Git哈希和真机stdout/stderr/退出码；CPU和OpenCL均实际文本生成。
- 建立独立进程随机区组Benchmark工具，分清warmup、共享KV、原生Timer、整进程wall和内存记账。Gate1共50正式CPU样本；最终CPU/GPU对照另取36样本，未拼接历史计算比值。
- 独立诊断分支缓冲逐Token时间，结合源码解释历史KV增长下Attention成本；已有Profiler把主要热点映射为量化线性投影。没有把必要计算包装为Runtime缺陷。
- 通过Adreno OpenCL设备事件验证主要模型计算，保留CPU回退和观测扰动边界。调查Hexagon/QNN仅限静态文档/源码，没有运行NPU。
- 第一层Q隔离、核验真实输入生命周期；独立重建ARMV86 INT8输入与原INT4权重、scale/offset、FMA和FP16后处理，**两输入共43,008元素与CPU Low输出完全一致**，解释约1%–2%浮点差异。不是原始未量化模型黄金验证，也不是Runtime修复。
- 冻结100条四类短任务及确定性评分器，两后端各100进程；CPU24%、GPU25%，共同失败74例。保持原Logits探索性失败和应用质量失败，不事后降阈值。

## 最终CPU/GPU执行特点

128+64：CPU Prefill/Decode 346.63/93.35 tok/s，GPU 1015.44/71.03 tok/s。三负载各后端n6，OpenCL Prefill较快、CPU Decode较快；均为同一固定资产和相同Token数量下的原生scope成本，输出内容并不等价。GPU模式580不是GPU线程数。此表不代表完整TTFT、端到端请求延迟或产品质量收益。

|输入+生成|后端|n|Prefill TPS 中位数 [min,max]|Decode TPS 中位数 [min,max]|Prefill/Decode CV%|Max RSS MiB 中位数|
|---|---|---:|---|---|---|---:|
|32+64|cpu|6|368.15 [343.24,574.19]|96.38 [95.36,97.98]|21.80/0.98|902.3|
|32+64|opencl|6|472.06 [469.50,473.18]|69.97 [68.02,72.50]|0.29/2.90|347.5|
|128+64|cpu|6|346.63 [340.15,528.46]|93.35 [90.82,94.57]|19.50/1.36|902.7|
|128+64|opencl|6|1015.44 [1011.75,1020.57]|71.03 [67.30,71.76]|0.37/2.34|347.0|
|128+256|cpu|6|339.97 [334.50,541.04]|89.73 [89.16,91.15]|22.13/0.91|902.5|
|128+256|opencl|6|1014.73 [1010.95,1021.13]|67.50 [67.30,68.37]|0.34/0.67|347.4|

完整范围、CV、配对时间比、温度/频率及限制见[最终对照报告](gate2d-comparison/Gate2D_CPU_GPU性能对照报告.md)。RSS是进程内存，不是GPU显存。

## 可复现的工具与证据

代码按实验职责保留：构建/部署、Benchmark采集、单调时钟缓冲Tracing、公共API算子/张量诊断、独立量化参照、冻结数据集与评分、离线统计和完整性核验。它们是本研究的实验工具，不是通用生产框架。诊断补丁仅在独立worktree，clean正式库与固定上游源码保留。

在Python标准库环境离线复核最终数据，不需要手机、不增加实验：

```powershell
python -B E:/DUANCE/gate2d-comparison/scripts/test_analysis.py
python -B E:/DUANCE/gate2d-comparison/scripts/analyze.py
python -B E:/DUANCE/gate2d-comparison/scripts/verify.py
python -B E:/DUANCE/verify_project.py
```

构建复现先看Gate0的实际configure/build日志和模型锁；GPU增量选项见C0/C1。各Gate README给出对应脚本和环境。本机WSL源码位于`/home/shawrange/src/MNN-3.6.2`。如在另一环境重跑，应另建副本、部署目录和新session，重新记录设备状态；不删除本归档冻结标记、补写或替换旧样本。性能数值不能保证跨驱动/系统/状态复现到同一绝对值。

## 模型质量限制与最终决策

当前发布量化资产、关闭Thinking提示及严格短文本应用契约不达标；失败含JSON代码围栏、标签/指令遵循和内容问题。100个人工用例不足以外推所有Qwen3模型，也没有独立未量化golden把共同失败分解成模型、量化或提示因素。GPU25%对CPU24%不能证明等价或GPU更优。

**停止当前选题并冻结**：保留可运行CPU/OpenCL实现及可信正、负结果；不提交没有依据的Runtime优化，不扩大诊断，不开展NPU或新的性能实验。未完成产品部署、上游PR或性能修复，不将跨后端成本优势写成自研优化提升。最终状态、文件清单与哈希见[PROJECT_FREEZE.json](PROJECT_FREEZE.json)、[project-manifest.json](project-manifest.json)。

## 阅读入口与附录

先读[最终技术报告](FINAL_TECHNICAL_REPORT.md)，面试准备见[INTERVIEW_GUIDE](INTERVIEW_GUIDE.md)，简历文字见[RESUME_PROJECT](RESUME_PROJECT.md)。下列原阶段报告是保留当时结论的历史附录，后续研究没有覆盖其原始证据。

|证据主题|报告入口|
|---|---|
|部署、构建和权重来源|[Gate0](gate0/Gate0_执行报告.md)|
|原生指标与CPU重复基线|[Gate1](mobile-llm-runtime-lab/Gate1_性能基线报告.md)|
|逐Token与KV/Attention机制|[Gate2-A](gate2-decode/Gate2_Decode执行机制研究报告.md)|
|算子级热点|[Gate2-B](gate2b-decode-hotspots/Gate2B_Decode热点归因报告.md)|
|驱动/OpenCL真实执行与NPU静态边界|[C0/C1](gate2c-opencl/Gate2C_OpenCL可行性报告.md)|
|跨后端数值定位|[C2](gate2c2-numerics/Gate2C2_CPU_GPU数值差异定位报告.md)|
|独立ARM量化契约复算|[C3](gate2c3-quant/Gate2C3_动态量化数值验证报告.md)|
|冻结任务质量验收|[C4](gate2c4-quality/Gate2C4_模型质量验收报告.md)|
|同会话最终成本比较|[Gate2-D](gate2d-comparison/Gate2D_CPU_GPU性能对照报告.md)|
