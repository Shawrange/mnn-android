# Gate 0 执行报告｜MNN 3.6.2 Android ARM64 CPU

日期：2026-11-08（America/Los_Angeles）。**Gate 0 通过：`llm_demo` 真机文本生成与 `llm_bench` 单次 CPU 烟测均实际成功，退出码均为 0。** 本次没有开始 Gate 1，没有修改 MNN tracked 源码，没有进行 Runtime 优化或 GPU/NPU 测试。

本报告为最新执行结果。此前的环境缺项与待执行命令保留在 [执行前核查记录](Gate0_执行前核查记录.md)，不能将其历史状态当作当前状态。

## 1. 九项任务验收

| 顺序 | 任务 | 实际结果与证据 |
|---|---|---|
| 1 | 安装 Linux Android NDK | r27c / `27.2.12479018`；官方 SHA-1 校验一致；Linux Clang 18.0.3 可执行。`evidence/installation/` |
| 2 | 获取完整 MNN 3.6.2 源码并固定 commit | 完整工作树 8,575 个 tracked 文件，浅克隆不含完整历史；tag 和 HEAD 均为 `7e3c6fb5225d3ccf22807ee641332669df34650d`，`git fsck` 成功、工作树干净。`evidence/source-checkout/` |
| 3 | Ninja ARM64 CPU 编译 | 459 个构建步骤完成；configure 与 build 退出码均为 0。`evidence/build/` |
| 4 | ELF / 依赖 / 构建参数检查 | 三个文件均为 ELF64/AArch64；两个 CLI 为 Android PIE，解释器为 `/system/bin/linker64`；CMakeCache、Ninja 实际命令和 readelf 输出均保存 |
| 5 | 模型下载和权重哈希 | 固定 revision 下载完整模型；图和权重 SHA256 匹配远端 LFS 对象，其余文件匹配 Git blob OID。`evidence/model-download/` |
| 6 | 部署小米15 | 专用 `/data/local/tmp` 目录部署成功；10 个运行相关文件的主机/手机 SHA256 全部一致。`evidence/runtime/*-deploy/` |
| 7 | `llm_demo` 实际文本生成 | 退出0，stderr为空；可读中文回答与提示相关，18个输入token、16个生成token。`evidence/runtime/*-demo/` |
| 8 | `llm_bench` 单次CPU烟测 | 退出0，stderr为空；JSON确认为 CPU / 4线程 / Low / 唯一 `pp128+tg64` 结果；`-rep 1`，另有工具内置一次warmup。`evidence/runtime/*-bench/` |
| 9 | 证据归档 | 原始stdout/stderr、每条ADB命令与退出码、构建命令/日志、模型及二进制哈希、手机端哈希、结果JSON均已保存 |

机器可读状态见 [verification-summary.json](evidence/verification-summary.json)。

## 2. 已验证环境与路径

| 项目 | 实际值 |
|---|---|
| WSL | Ubuntu 26.04.1 LTS / x86_64 / WSL2 |
| Git / CMake / Ninja | 2.53.0 / 4.2.3 / 1.13.2 |
| Linux NDK | `/home/shawrange/Android/android-ndk-r27c` |
| 目标编译器 | NDK `toolchains/llvm/prebuilt/linux-x86_64/bin/clang++`，18.0.3 |
| 完整源码 | `/home/shawrange/src/MNN-3.6.2` |
| 构建目录 | `/home/shawrange/src/MNN-3.6.2/build-android-arm64-cpu-gate0` |
| Windows产物副本 | `E:\DUANCE\gate0\staging` |
| 模型目录 | `E:\DUANCE\gate0\assets\Qwen3-0.6B-MNN` |
| ADB | `C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe`，37.0.1 |
| 手机 | Windows USB名称 Xiaomi 15；型号 `24129PN74C`；序列号 `ee19377b`；状态 `device` |
| SoC / 系统 | `SM8750` / Android 16 / API36 / `OS3.0.307.0.WOCCNXM` |
| ABI / 页大小 | `arm64-v8a` / 4096字节 |
| 内核报告可管理内存 | MemTotal `15476168 kB`，约14.76GiB；不是进程RSS |
| 手机运行目录 | `/data/local/tmp/mnn-gate0-20261108T134731469951Z` |

未依赖主机CUDA、PyTorch、Gradle、Java或WSL ADB。没有root、改系统镜像或修改手机安全设置。Linux NDK只安装到WSL用户目录，没有修改全局NDK配置或代理配置。

## 3. 构建参数与 ELF 结果

核心配置：`Release`、C++17、`arm64-v8a`、`android-21`、`c++_static`、Ninja、并行4。

- 开启：`MNN_BUILD_LLM`、`MNN_LLM_BUILD_DEMO`、`MNN_LOW_MEMORY`、`MNN_SUPPORT_TRANSFORMER_FUSE`、`MNN_ARM82`、MNN自带线程池。
- 关闭：`MNN_SEP_BUILD`、`MNN_SME2`、`MNN_KLEIDIAI`、OpenCL/OpenGL/Vulkan/CUDA/QNN/Hexagon/NNAPI/HiAI NPU、Omni/Diffusion、OpenCV/Audio附加模块、训练、通用测试、通用benchmark、converter。
- 通过CMake链接参数为可执行文件与共享库加入 `max-page-size=16384`、`common-page-size=16384`；三个ELF的LOAD段实际均为`0x4000`对齐。本次手机页大小为4KiB，**未在16KiB页设备上验证运行**。
- `MNN_BUILD_BENCHMARK=OFF` 不影响 `llm_bench`，后者由LLM engine/demo/tools构建入口创建。

完整配置见 [configure.command.txt](evidence/build/configure.command.txt)、[CMakeCache.txt](evidence/build/CMakeCache.txt)、[ninja-commands.txt](evidence/build/ninja-commands.txt)，检查汇总见 [inspection-summary.json](evidence/build/inspection-summary.json)。

| 产物 | 字节数 | 实际动态依赖 |
|---|---:|---|
| `llm_demo` | 35,096 | `libMNN.so`、`liblog.so`、`libm.so`、`libandroid.so`、`libdl.so`、`libc.so` |
| `llm_bench` | 120,944 | 同上 |
| `libMNN.so` | 5,014,312 | `liblog.so`、`libm.so`、`libandroid.so`、`libdl.so`、`libc.so` |

除`libMNN.so`外均由Android系统提供；无`libllm.so`、`libMNN_Express.so`或`libc++_shared.so`依赖。`MNN_USE_LOGCAT=OFF`仍可存在`liblog.so`链接依赖，以ELF实际NEEDED结果为准。产物已strip，仅用于Gate 0；本次没有宣称是源码调试/Profiling构建。

二进制SHA256：

```text
37e65f0a8881699ec22bc96dd3ec2457c00ec3699ff2e4a7ef810ca8b1b915d9  llm_demo
fd85bf65a75656d023feb9e2ad315f6ee7c6033c8f1591a835e54d2985db4676  llm_bench
47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e  libMNN.so
```

## 4. 模型资产与来源边界

模型：[taobao-mnn/Qwen3-0.6B-MNN](https://huggingface.co/taobao-mnn/Qwen3-0.6B-MNN)，revision **`34dfccda1187ded6e07ea06426da576b0b793c6b`**。模型卡声明Apache-2.0和4-bit量化。完整包包含`config.json`、`llm_config.json`、`llm.mnn`、`llm.mnn.weight`、`tokenizer.txt`等；该发布包不需要额外补`tokenizer.mtok`或独立embedding文件。

本地实际校验结果：

```text
d426c65a5159c938ccc237cdfbd982137f276804f27b414ca0ecf3fc0a660f8c  llm.mnn
953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f  llm.mnn.weight
```

分别为461,520和450,810,338字节；均与远端LFS对象SHA256一致。其余下载文件也以远端Git blob OID校验。详见 [files.json](evidence/model-download/files.json)、[model-files.sha256](evidence/model-download/model-files.sha256)、[model-lock.json](evidence/model/model-lock.json)。

运行时另建`config.cpu.json`，保留原始`config.json`：固定CPU、4线程、Low precision/memory、greedy、最多64个新token、关闭reuse_kv与async。Demo通过第五个位置参数关闭Qwen3 thinking；benchmark按上游自身逻辑使用greedy和ignore_eos。

**来源限制仍需保留**：这是预转换发布模型，本次没有自行导出；发布者完整导出参数和exporter commit没有披露，仍记录为null。本次证明该固定资产与MNN 3.6.2的部署兼容性，不证明能够从原始Qwen checkpoint逐字节重建同一量化资产，也不完成准确率评测。

## 5. 真机运行命令与观察

以下命令在手机端的上述运行目录中实际执行，均使用本次构建及校验的产物：

```bash
LD_LIBRARY_PATH=. ./llm_bench --help
LD_LIBRARY_PATH=. ./llm_demo Qwen3-0.6B-MNN/config.cpu.json prompt.txt 64 no_thinking
LD_LIBRARY_PATH=. ./llm_bench -m Qwen3-0.6B-MNN/config.cpu.json \
  -a cpu -t 4 -p 0 -n 0 -pg 128,64 -rep 1 \
  -c 2 -mmp 0 -qa 0 -fa 1 -load false -j bench-smoke.json
```

Demo提示：`请用一句话介绍北京。`（UTF-8无BOM，文件有末尾换行）。实际生成：

> 北京是中国的首都，拥有丰富的文化和历史，是重要的国际城市。

实际记录18个prompt token、16个生成token。人工阅读与原始UTF-8解码均确认文本正常；Demo stdout中的耗时/速度不是本次验收依据。纯文本模式输出的`audio RTF = nan`是未使用音频指标，未当作LLM运行失败或有效音频数据。

Benchmark回收JSON确认：`backend=CPU`、`threads=4`、`precision=2`、`memory=2`、`quantKv=0`、`flashAttention=1`，唯一结果为`prefill_and_decode`、`prompt_len=128`、`generate_len=64`。`-p 0 -n 0`确保没有额外执行默认独立pp/tg工作负载。

**样本边界**：`-rep 1`实际含1次不计入结果的warmup和1次有效测量；输出中的`±0.00`不代表性能稳定。JSON中保留了原始吞吐值，本报告不据此给出可信性能基线、P50/P95、性能收益或硬件泛化结论。Benchmark使用合成token，文本正确性依据来自另跑的Demo。

CPU执行依据为：本次CPU构建的CMakeCache/二进制哈希、后端配置映射到CPU、模型配置、实际bench CPU标签及JSON；没有借由SoC型号推断NPU执行。ARM82 FP16属于CPU路径。本次没有进一步做算子级trace或ISA命中审计。

## 6. 证据索引

| 类型 | 路径 |
|---|---|
| 最终状态与范围 | `evidence/verification-summary.json` |
| NDK官方清单、下载/安装日志、退出码、校验 | `evidence/installation/` |
| 源码pin、fsck、checkout与失败尝试 | `evidence/source-checkout/` |
| 配置、构建日志、退出码、ELF、flags、产物哈希 | `evidence/build/` |
| 模型下载日志与退出码 | `evidence/model-download.log`、`evidence/model-download.exit.txt` |
| 模型逐文件校验 | `evidence/model-download/` |
| 部署、10文件主机/设备哈希对照 | `evidence/runtime/20261108T134731469951Z-deploy/` |
| 真实help | `evidence/runtime/20261108T134819702391Z-help/` |
| 文本生成原始stdout/stderr、退出码 | `evidence/runtime/20261108T134836909994Z-demo/` |
| CPU烟测原始stdout/stderr、退出码、JSON | `evidence/runtime/20261108T134933291729Z-bench/` |
| 设备系统信息 | `evidence/device/device-metadata.json` |
| 证据文件校验总表 | `evidence/evidence-files.sha256` |

每个runtime目录包含`commands.json`，保存完整ADB参数、开始时间、经过时间与每条命令退出码。stdout/stderr以原始字节保存，未剔除警告或改写失败输出。

## 7. 复现入口与兼容记录

构建脚本为 [build_android_cpu.sh](build_android_cpu.sh)，只构建、不改MNN源码。已存在构建目录时脚本会拒绝复用CMakeCache，需指定新目录：

```bash
export ANDROID_NDK=/home/shawrange/Android/android-ndk-r27c
bash /mnt/e/DUANCE/gate0/build_android_cpu.sh \
  /home/shawrange/src/MNN-3.6.2 \
  /home/shawrange/src/MNN-3.6.2/build-android-arm64-cpu-gate0-repro
```

[run_device.py](run_device.py)的`deploy`、`help`、`demo`、`bench`模式分别执行一个阶段。重新部署会建立新的手机目录，并记录新的时间戳日志；执行前仍需核对设备序列号和模型/二进制来源。

实际遇到并保留的兼容情况：

- **WSL网络直连超时**：WSL Git克隆停滞，限时GitHub请求超时；终止该Git进程的退出码为143，日志保留。改用Windows Git下载同一tag的bare仓库对象，再以Linux Git离线检出完整工作树，重新核对commit/tag/fsck和清洁状态。未关闭TLS校验，未修改系统代理。
- **CMake 4.2.3**：出现旧最低版本的deprecation提示，但本次真实configure/build成功，无需降级或修改上游CMake。
- **编译警告**：保留上游格式类型等警告；没有为消除警告更改核心源码。
- **Windows控制台编码**：首次聚合console显示中文乱码；原始ADB stdout为有效UTF-8且正文正常。读取原始文件确认后，后续Python console显式UTF-8。未因展示编码问题重跑模型或改写原始输出。
- **模型旧README**：包含已删除的`MNN_CPU_WEIGHT_DEQUANT_GEMM`参数；实际构建未使用该选项。

官方源码与文档入口仍固定到同一commit：`project/android/build_64.sh`、根`CMakeLists.txt`、`transformers/llm/engine/CMakeLists.txt`、`engine/demo/llm_demo.cpp`、`engine/tools/llm_bench.cpp`、`engine/src/llm.cpp`、`source/backend/cpu/CPUAttention.cpp`、`CPUKVCacheManager.cpp`。详细函数/行号与官方链接见执行前核查记录第8节。本次只完成可运行性验证，未开展执行链瓶颈诊断。

**结束状态：Gate 0完成；Gate 1未开始；Runtime核心修改为零。**
