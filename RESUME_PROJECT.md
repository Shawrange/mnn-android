# 简历项目材料｜可证据核验版本

## 项目名称

Android端侧LLM Runtime执行机制与CPU/OpenCL对照研究（个人工程研究项目，已冻结）

## 技术栈

C++ / Python / MNN3.6.2 / Android ARM64 / NDK r27c / CMake / Ninja / ADB / OpenCL / ARMV86量化路径；小米15 Snapdragon8 Elite / Adreno830。固定Qwen3-0.6B-MNN发布量化资产。

## 简历正文建议

- 基于固定MNN源码完成Android ARM64 CPU与Adreno OpenCL真机推理，建立版本/权重锁定、ELF依赖及设备端SHA256核验、原始日志与退出码归档工具。
- 建立随机区组独立进程Benchmark与设备状态记录，完成50组CPU正式样本和36次同会话CPU/GPU有限对照；区分warmup、Prefill/Decode scope、整进程RSS与端到端指标，发现本配置GPU Prefill、CPU Decode分别具备执行成本优势。
- 在独立诊断分支缓冲逐Token/Attention/KV事件，结合现有Profiler将Decode主要热点映射到197个量化线性投影；用源码与受控实验解释KV增长成本，保留观测扰动及设备混杂边界。
- 针对第一Q投影独立实现ARMV86动态INT8输入、INT4权重与FMA/FP16后处理参照，在两固定输入共43,008输出元素上精确复现CPU Low，解释约1%–2%浮点差异，避免误判Backend缺陷。
- 冻结100例短文本任务与确定性评分规则，完成CPU/GPU配对评估及固定前缀Logits诊断；如实记录固定配置成功率24%/25%未达应用门槛，并据证据停止优化、冻结交付。

## 更短版本（三条）

1. 完成MNN Android CPU/OpenCL部署及真实GPU事件验证，构建、模型、二进制与运行证据按哈希归档。
2. 实现随机区组性能采集、最小逐Token观测和独立量化复算，覆盖50组CPU基线、36次CPU/GPU对照及43,008元素精确数值复现。
3. 以100例冻结任务量化质量边界，区分执行成本与应用收益；没有确认需修复的Runtime问题，完成技术报告和可复核工具后冻结项目。

## 面试补充性能口径

128+64：CPU Prefill/Decode 346.63/93.35 tok/s，GPU 1015.44/71.03 tok/s，每cell6独立进程。数值是固定输入/生成数下原生Benchmark scope，并非产品级收益、完整TTFT或用户E2E。所有比较来自同会话，不拼历史CPU；不是本人优化带来的提升。

## 明确不应写入简历的内容

不得写“优化MNN使推理提升X倍”“修复ARM量化Bug”“自研KV Cache/Attention Kernel”“适配NPU并加速”“已提交上游PR”“产品成功上线”或“GPU质量验收通过”。没有这些成果。Tracing/采集补丁是诊断工具，不是Runtime优化。43,008元素是两个输入的局部路径验证，不是43,008条评测样本；100例也不代表通用模型质量基准。

## 核验入口

根README、FINAL_TECHNICAL_REPORT、各Gate报告；Gate2-D `analysis/samples.csv`、`analysis/paired-ratios.csv`，C3独立参照及真实输入/metadata，C4 `freeze.json`与逐例评分。完整文件哈希由根`project-manifest.json`和`verify_project.py`核验。
