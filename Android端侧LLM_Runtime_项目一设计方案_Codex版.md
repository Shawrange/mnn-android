# 项目一设计方案｜Android 端侧 LLM Runtime 性能分析与工程改进

> 版本：项目设计稿 v0.1；日期：2026-11-08。本文是**待实施的计划**，所有优化、跑分、后端可用性均未在用户设备上实测。目标为 2027 届 OPPO／华为终端等端侧推理系统研发实习或校招；**不以实现聊天 App、完成教程或获得某个加速倍数作为成功定义**。

## 0. 一页决策

| 项目 | 决策 |
|---|---|
| 职业对应 | R：端侧推理框架／Runtime 研发（主）；D：端侧模型部署与性能优化（补充）；T：性能工程（补充） |
| 框架 | MNN，初始基线使用 3.6.2 发布版本，固定精确 git commit；实际构建以**该提交源码和 `--help`**为准 |
| 主要设备 | 小米 15（骁龙 8 Elite，Android ARM64）；主机 Windows + RTX 4060 Ti 8GB，WSL2 Ubuntu 作为编译/分析环境 |
| 基准模型 | Qwen3-0.6B；精度及转换配置固定，精度路线调整时建立**独立配置组** |
| 第一后端 | ARM CPU：必须成功、可重复、可调试 |
| 增强后端 | OpenCL GPU：确认模型/算子支持后开展；Hexagon / QNN NPU：分别验证且作为条件项 |
| 主问题 | 手机端真实负载下 Prefill／Decode／KV Cache／Runtime 内存与执行路径的可归因开销 |
| 项目边界 | 只围绕**一个经 Profiling 验证的具体问题**完成源码级工程改进；不自造大型推理引擎，不增加无关聊天 UI |
| 保底成果 | 固定环境、可复现运行、执行链路分析、可信基线、能解释的瓶颈或限制；如无根因应如实说明 |
| 理想成果 | Runtime 源码修复／优化／实际有维护价值的测试工具，包含正确性、端到端对照及适用范围；可提交上游 PR，但不以合并为硬指标 |

## 1. 为什么这是主项目

**岗位对应而非技术堆栈：** OPPO 2027 届「深度学习工程师」官方职责包括手机端 LLM/MLLM 推理框架研发及性能优化、功能测试与性能评估工具、高通/MTK NPU SDK 部署优化。项目一针对其中的 Runtime 与性能工具；对特定 NPU SDK 的证明力取决于是否**实际完成该后端测试**。华为云推理框架与昇腾算子可兼投，但本项目**不自动证明**分布式请求调度或 Ascend C 开发。

**为什么不是单纯 Android Chat Demo：** 仅有 SDK 调用和 UI，不能证明执行图、内存资源、Backend、C++ 系统研发。面试能直接追问的材料应为：调用路径图、最小复现、Profiling 证据、代码 diff、测试和结果边界。

**为什么不从零造引擎：** 成熟开源引擎中的真实问题更能体现源码阅读、系统兼容性、正确性与工程维护能力。项目的真实性、岗位匹配度和竞争差异化需分别评估。

## 2. 技术范围及设备路径

### 2.1 Host 与目标设备

- 主机：Windows 11（或现有 Windows）+ WSL2 Ubuntu。源码、构建缓存和测试工具建议放在 WSL 的 Linux 文件系统；USB 设备的 ADB 连接根据实际环境由 Windows ADB 或 WSL ADB 管理，**不要让两套 ADB 服务同时争抢设备**。
- 编译：Android SDK/NDK、CMake、Clang、Python；版本以 MNN 固定提交和 Android 示例所需版本为准。
- 手机：小米 15，启用 Android 开发者选项与 USB 调试即可开展常规 ADB 部署；**不以 root、关闭系统安全保护或修改系统镜像为前提**。
- 测试环境：记录系统版本、设备 SoC、内存容量、MNN commit、模型哈希、Android ABI、编译优化选项、后端、线程数、App/CLI 模式。

### 2.2 三种后端的边界

| 路径 | 必须达到 | 明确限制 |
|---|---|---|
| CPU | Qwen3-0.6B 量化模型可推理、官方 benchmark 跑通、源码分析可达执行路径 | 有 Android 真机证据，但不能推出 GPU/NPU 能力 |
| GPU/OpenCL | 后端加载成功，记录真实算子执行及输出正确性，建立独立基线 | 不假定整个模型都在 GPU；OpenCL 初始化和 tuning 要与稳定运行分开 |
| NPU/Hexagon 或 QNN | 首先验证 SDK/模型格式/实际执行，明确是 MNN 直接 Hexagon 还是 QNN SDK 方案 | 不能将 Hexagon 与 QNN 混为一谈；未获取 SDK 或后端回退，必须停在「不可验证」 |

MNN 官方文档中，Hexagon LLM 途径要求针对性模型导出：`--quant_bit 4 --quant_block 64 --sym`，并使用相应 Transformer C4 路径。QNN 方案则有单独的 SDK、构图与部署依赖。**这两种路径的模型产物和执行条件可能不同；跨后端结果只能先称作“完整部署配置比较”，不能未经控制直接归因为硬件或精度单因素提升。**

## 3. 可交付的工程架构

建议采用**两个关联仓库**：一个自己的研究与实验仓库；一个 MNN fork 用于提交最小源码改动。自己的实验仓库记录 MNN 的上游 commit、fork commit 和差异，而不直接复制大量上游代码或提交模型权重、专有 SDK。

```text
mobile-llm-runtime-lab/
├── README.md                    # 研究问题、已完成/未完成、复现实验入口
├── AGENTS.md                    # Codex 规则与项目边界
├── configs/
│   ├── workload.cpu.yaml       # 固定模型、token负载、CPU线程等
│   └── device.schema.json      # 设备及后端元数据字段
├── scripts/
│   ├── check_environment.py    # 校验 adb / model / commit / 依赖
│   ├── run_bench.py            # ADB与MNN benchmark运行入口
│   ├── collect_metadata.py     # 每次实验采集系统版本等信息
│   └── summarize.py            # 原始样本汇总与区间估计
├── tests/
│   ├── test_bench_parser.py
│   ├── test_config_validation.py
│   └── fixtures/              # 伪造的bench输出样本，供离线测试
├── docs/
│   ├── build.md
│   ├── execution_trace.md      # Prefill/Decode/KV等实际调用路径
│   ├── methodology.md         # 指标定义、样本数、热状态、A/B设计
│   ├── experiments.md         # 基线及每次假设记录
│   └── result_boundaries.md   # 后端真实性、限制与不确定性
├── results/
│   └── README.md               # 只存小型结果；大文件使用ignore
├── reports/
│   └── final_report.md
└── .gitignore

MNN-fork/                       # Fork上游MNN；每个源码优化独立分支
```

### 实验元数据最低要求

`timestamp, device_model, soc, android_version, mnn_commit, fork_commit, model_name, model_checksum, export_args, backend_requested, backend_confirmed, build_flags, thread_count, workload_id, prefill_tokens, generated_tokens, iteration, warmup_policy, raw_latency_or_throughput, thermal_observation, result_status`。

另设字段 `evidence_status`: `measured / build_only / unsupported / inferred`，避免把编译成功当成真机执行成功。

## 4. 分阶段实施与验收（允许分支，不强求“发现Bug”）

### Gate 0｜工程与后端可行性

**目标：**固定版本，验证设备接入、模型资产、编译与运行路径。

任务：

1. 记录 MNN 3.6.2 tag 与精确 commit、官方 README/文档路径、构建选项与工具 `--help` 输出；如 tag 与 master 文档有差异，以固定版本为准。
2. 使用官方 LLM Demo 在主机或 Android 设备上验证 Qwen3-0.6B 模型可正常生成。模型来源、许可、权重哈希和导出参数必须记录。
3. 在小米15上用 **ARM CPU** 跑通 `llm_bench`，保留日志和源码版本；记录 CPU 路径的正确执行证据。
4. 列出 OpenCL 与 Hexagon/QNN 的必要依赖；只做“可用性调查”，不强制完成 NPU。

**通过标准：**环境文档能使第三方复现 CPU 推理；输出内容可检查、命令可追溯。**未通过时，不进入性能优化。**

### Gate 1｜可信性能基线（L1-A）

**目标：**测量真实负载，而不是只贴一个 `tok/s`。

固定四类工作负载：

| 负载 | 建议条件（需核对真实token数） | 目的 |
|---|---|---|
| A | 128-token prompt + 64-token decode | 交互响应场景 |
| B | 512 + 64 | 中等Prefill |
| C | 1024 + 128 | 长上下文对解码的影响 |
| D | 多轮上下文逐渐增长 | KV复用、分配与持续稳定性 |

测量：

- `Prefill tok/s`、`Decode tok/s`（必须在真实 KV Cache 长度条件下）、总任务延迟、可实现情况下的 TTFT；**不能用 `-n` 的极短 KV 条件冒充真实 Decode 性能**。
- 冷加载与热加载分开；OpenCL 首次 tuning 与稳定运行分开。
- 内存明确使用 RSS、PSS 或进程内 allocator 计数中的哪一种；多种指标不得混写。
- 每组保留原始采样、有效样本数、环境状态及异常样本规则。记录 P50/P95；若比较细小差异，可做交替 A/B 与配对差值、Bootstrap 置信区间；样本不足时明确“不足以证明收益”。
- 不要求获得不受支持的硬件功耗数据。读取温度/频率若被系统限制，应明示缺失而非估算为精确功耗。

MNN `llm_bench` 文档提供 `-pg <prefill,decode>` 与 `-rep`；**实际参数与输出解析要先以固定版本 `./llm_bench --help` 检查**。参考（仅在固定版本确认支持时执行）：

```bash
./llm_bench -m /path/to/model/config.json \
  -a cpu -t 4 -pg 128,64 -rep 5
```

**通过标准：**数据可重复采集、能解释每个指标的定义与测量边界；此时只称“完成基线与执行分析”，**不称已优化Runtime**。

### Gate 2｜源码执行链与诊断（L1-B，条件达到）

**目标：**沿实际调用链找到发生开销的模块，对候选假设作反证。

研究线索（以固定版本源码为准，不假定文件路径稳定）：

- `transformers/llm`：模型加载、Tokenizer、Prefill/Decode、生成与 KV 状态。
- `express`：表达式/计算图路径与执行组织。
- `source/backend/cpu`、`source/backend/opencl`：实际算子、调度与资源分配。
- `source/backend/hexagon` 或 QNN 相关模块：**仅在实际验证可用后**继续。

优先**只选一个问题**：

1. **实际执行路径中的额外开销**：例如不必要的拷贝、重复初始化或缓冲区分配（需证据）。
2. **连续会话的内存与资源生命周期**：检查缓存复用、reset、释放、异常路径（需测试）。
3. **CPU/GPU执行路径的性能差异**：如果实际观测有异常，定位其在初始化/执行/传输中的来源（不可仅凭总时延下结论）。

使用函数计时/轻量 Profiling 的诊断构建，配合源码阅读与必要的系统性能工具。**Profiling instrumentation 的开销要与正式性能测量隔离**。

**通过标准：**至少一张调用路径图、一份可证伪的假设记录、一个可重复测量或最小复现。如果尚未确认根因，只称 L1-A；根因证据充分才称 L1-B。

### Gate 3｜源码贡献或质量工程（按岗位类型验收 L2）

**目标：**对已确认问题做最小可维护改动。

可选工程成果，不预先承诺某项必有收益：

- A. 修复 Runtime 内存、生命周期、异常恢复或执行正确性问题。
- B. 减少可复现的重复工作、无效分配或不必要数据复制，且整模型验证收益。
- C. 做具有明确维护需求的性能回归与自动化测试工具，能够发现真实回归，特别适合测试性能工程岗位；**不能把纯工具成果自动称为核心 Runtime 优化**。

提交要求：

- Issue / 问题描述 + 最小复现、根因与对照证据。
- 保持对已有后端/数据类型/异常路径的正确性；新增回归测试。
- 记录不同输入长度、运行模式、设备条件下的适用范围与回退行为。
- 性能实验至少含组件级与**整模型级**；不以微基准加速代替真实端到端收益。
- 代码更改应是可以独立审阅的最小 PR，不要为一个问题大范围重构。

**通过标准：**正确性验证通过，变更理由清晰，收益/代价/适用边界可复现。无稳定性能收益时也可以得出否定结论；如果缺陷并不适合修改，回退至 L1 可信诊断成果。

### Gate 4｜外部质量与求职证据（可选 L3）

1. 维护个人 fork 中的精简 PR；若适合上游，提交 MNN PR / Issue。
2. 保留 Code Review、独立复现或维护者反馈；不要把“Open PR”宣传成“已合并”。
3. 输出完整报告：问题→证据→机制→方案→代码→正确性→性能→边界→与岗位关联。

## 5. 测量设计与防止误导的规则

1. **真实 token 工作负载：**记录 tokenizer 输出的 token 数而不是用字符长度代替；多轮使用真实 KV Cache；同一 Prompt Template 与采样规则固定。
2. **实验配置控制：**先在同一个模型产物、同一个硬件后端下对比“修改前 vs 修改后”；更换量化格式/后端则视为另一个部署方案，不能直接称作单因素优化。
3. **热状态：**禁用不必要的后台负载、记录充电/电量/环境、间隔运行以减少热衰减；不要求冒险强制高频或长时间过热压测。
4. **冷/热：**设备无 root 时难以完全控制 OS 文件缓存，不能把普通重新启动程序声称为“严格冷缓存”。
5. **统计：**每组保留原始数据，预定义异常样本规则。若 P95 不稳定，先增加合适样本，而不是只挑最好的一次。
6. **真实性：**每个结论附 `设备—后端—指标—验证方式`；日志中 backend 指定成功不一定等于算子确实由该设备执行；需日志/Profiler/trace支持。
7. **验收优先级：**正确性 > 有效可复现 > 来源可追溯 > 性能增益。禁止伪造或人为挑选数据。

## 6. Codex 配合方式：把 AI 当成可审阅的协作开发者

### 6.1 分工原则

| 由 Codex 协助 | 必须由人审核或实测 |
|---|---|
| 浏览源码并输出带文件/函数名的调用图草案 | 逐点核对实际代码，确认调用图真实 |
| 搭建可参数化 Bench 工具、解析器与单元测试 | 验证真实手机输出格式、ADB环境、指标语义 |
| 生成最小重现测试草案和候选补丁 | 判断根因、修改设计、正确性与性能证据 |
| 写文档、统计脚本和对照报告草稿 | 所有硬件数据必须来自真实实验，确认统计结论 |

**不可交给 Codex 自行决定：**更换研究目标、忽略编译错误、删掉失败测试、写虚构测速、从外部下载未核验的 SDK、以 unsafe 方式修改手机系统。

### 6.2 放入研究仓库根目录的 `AGENTS.md` 建议内容

```markdown
# Project Rules for Codex
- This repository studies **MNN Android on-device LLM Runtime** on Xiaomi 15.
- Primary evidence target: C++ runtime execution path, correctness, reliable Android measurements.
- Pin MNN to a precise commit. Do not assume master APIs match this commit.
- Never fabricate measurements, device states, benchmark outputs, review status, or PR acceptance.
- Do not claim NPU execution from SoC model alone; verify backend and operator placement.
- Work in small, reviewable changes; one issue per branch. Keep upstream changes minimal.
- Before implementing a change: state hypothesis, affected source files, test plan, and fallback.
- After implementing: report exact changed files, how to build/test, passing/failing tests, limitations.
- Bench scripts preserve raw outputs and hardware metadata; no auto-deletion of failed samples.
- Do not commit model weights, proprietary Qualcomm SDK binaries, keys, or personal phone data.
- Do not root the phone or change system security settings as part of experiments.
- Ask for user review before any broad refactor or any patch to NPU/DSP low-level code.
```

### 6.3 可直接复制给 Codex 的四个任务

**任务 1——只做仓库侦察，不写业务改动：**

> 你是端侧推理系统工程师。请先检查我本地 MNN 仓库的固定 commit 与官方文档，列出 Android ARM64 编译 LLM Demo 和 `llm_bench` 的实际依赖、构建入口和参数。请输出：①环境核对清单；②针对小米15的 CPU 后端最小可执行路径；③仓库中真实存在的相关文件和函数位置；④版本与文档可能不一致的点。不得假设编译成功，不得修改核心源码或编造命令运行结果。

**任务 2——搭建测试工具，严格保留原始证据：**

> 在 `mobile-llm-runtime-lab` 中实现可配置的 adb benchmark runner，支持 CPU 后端、固定 model config、工作负载、线程数、重复次数。每次运行要保存完整 stdout/stderr、退出码、版本和设备元数据。解析器必须有 fixtures 单元测试；未解析字段写 null，不要猜测。只生成工具与测试，不修改 MNN Runtime。完成后输出测试命令、测试结果及已知限制。

**任务 3——源码阅读与性能根因：**

> 基于实际可运行的单个 Qwen3-0.6B CPU 工作负载，追踪从 LLM 入口到 Prefill / Decode / KV Cache / 后端执行的真实调用链。给每个结论标注源码文件与函数名。请提出最多三个可证伪的性能或资源开销假设，以及需要的最低侵入性测量方式。此任务不允许直接提交优化代码，也不能把猜想写成已确认的瓶颈。

**任务 4——一个最小补丁：**

> 我已经提供固定的 commit、实测日志、明确的根因及回归场景。请先提出不超过两种最小修改方案、正确性风险、性能指标和回退策略。经我选择后仅实现一个最小补丁，并添加测试。输出源码 diff、实际运行过的测试、未运行的测试及结果。不得编造手机性能收益；如果没有实验数据，结论写“待真机验证”。

## 7. 第一轮最小行动清单

1. 在 WSL2 中准备 Git/CMake/NDK/Python；由 Codex 检查**当前固定版本**的具体构建入口与依赖。
2. fork MNN、确定 3.6.2 的 commit，记录 Android 示例仓库文档版本。
3. 在小米15上通过 ADB 跑通最简单的 ARM64 原生可执行程序及 MNN CPU LLM Demo。
4. 记录 Qwen3-0.6B 模型来源、许可、导出设置和 SHA256；模型本体不提交 Git。
5. 获取 `llm_bench --help` 的原始输出，确认 `-pg`、重复次数、profile 开关和真实输出格式。
6. 将一个固定工作负载的原始日志、配置、设备信息归档。
7. **到此先验收 Gate 0，不要让 Codex 直接“优化源码”。**

## 8. 面试中如何展示，而不是堆功能

最终材料至少应覆盖三个层面：

- **系统理解：**手绘或经核验的 MNN LLM 执行路径，解释 Prefill/Decode/KV Cache、Backend 选择与内存生命周期。
- **工程可信度：**固定 commit、原始 benchmark 数据、样本数、正确性回归、失败场景与不能推广的限制。
- **个人贡献：**明确哪些是上游已有代码、哪些是自己修改；能解释为何改动、替代方案、性能收益及维护代价。

简历描述只使用完成过的事实。若仅达到 Gate 1，写“建立真实设备性能基线和执行链路分析”；若完成真实 Gate 3，才写“优化了某执行路径并经验证改善某指标”。

## 9. 第二个项目的候选——只作为后续选择池

| 排名 | 方案 | 做到何种技术深度才值得单独写在简历 | 补充岗位 |
|---|---|---|---|
| 1 | **Android Camera 实时视觉推理 Pipeline**（ncnn/ExecuTorch） | 不仅做 Camera→YOLO Demo；定量分析采集→YUV/RGB处理→图像缩放→推理→后处理→画面呈现的端到端延迟，完成线程、Buffer复用或拷贝优化；在真机持续运行验证 | OPPO影像/CV模型部署、端侧系统与产品落地 |
| 2 | **ncnn ARM算子优化** | 确定具体算子/shape的 Profiling 瓶颈；实现对比策略/最小 C++或NEON改动，验证算子与整模型两层，明确 CPU 型号与适用边界 | CPU后端、算子、异构计算 |
| 3 | **ExecuTorch + Qualcomm QNN 部署** | 真实完成模型导出、算子覆盖和NPU运行验证，给出准确率—延迟—内存对照及 fallback/图分割分析，而非只转模型格式 | OPPO高通NPU、部署性能 |
| 4（条件） | **手机实时语音链路**（VAD→ASR→简单意图处理） | 在真实麦克风输入下研究缓冲区、低延迟分帧、模型并发与端到端延迟；实现系统改进 | 端侧多模态产品、语音与系统工程 |

第二项目不应与第一个重复做一遍 Qwen 模型加载。优先选择能增加 **视觉/传感器输入、真实业务 Pipeline 和端到端系统优化** 能力的方案；如果面试反馈明确偏 CPU/算子，再切换为 ncnn 算子方向。

## 10. 参考来源（资料用于定义范围，不表示已在用户设备上通过）

- MNN releases（3.6.2，2026-10）：https://github.com/alibaba/MNN/releases
- MNN LLM 导出、Android Hexagon 与 `llm_bench` 文档：https://github.com/alibaba/MNN/blob/master/docs/transformers/llm.md
- MNN QNN 及 NPU 后端文档：https://github.com/alibaba/MNN/blob/master/docs/inference/npu.md
- MNN Android LLM App 构建参考：https://github.com/alibaba/MNN/blob/master/apps/Android/MnnLlmChat/README_CN.md
- OPPO 2027届深度学习工程师（手机端LLM/MLLM Runtime）：https://careers.oppo.com/university/oppo/campus/post/1773?recruitType=Graduate
- OPPO 2027届计算机视觉算法开发工程师：https://careers.oppo.com/university/oppo/campus/post/1857?recruitType=Graduate
- ncnn 官方项目：https://github.com/Tencent/ncnn
- ExecuTorch 官方 Android / Qualcomm 后端文档：https://github.com/pytorch/executorch/blob/main/docs/source/using-executorch-android.md

> **结论**：第一个项目的首要完成条件是「能在小米15上、在固定 MNN 版本和真实模型上，稳定复现 CPU LLM 执行并获取可信测量」。在此基础上，用 Codex 辅助阅读调用链、搭建自动化实验，再针对一个实证问题做局部源码改进。GPU/NPU 是增益，不是未经验证的承诺。
