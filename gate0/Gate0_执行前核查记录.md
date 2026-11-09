# Gate 0｜MNN 3.6.2 Android ARM64 CPU 可行性核查

检查日期：2026-11-08（America/Los_Angeles）。依据：已完整阅读工作区《Android端侧LLM_Runtime_项目一设计方案_Codex版.md》，并读取官方固定提交的真实源码、构建脚本、仓库内官方文档及模型发布元数据。

**结论：源码层面存在可行的最小路径：WSL2 Linux NDK 交叉编译 → ARM64 原生 CLI → Windows ADB → 小米15 CPU。当前 Gate 0 尚未通过。** 本次完成版本与源码核查、环境探测和可复现步骤准备；没有 Android 编译成功记录、实际生成输出或真机 benchmark。没有改动 Runtime 核心代码，没有开启 GPU/NPU 优化，没有安装系统包或下载权重。

## 1. 固定版本与证据范围

| 项目 | 实际核查结果 |
|---|---|
| 官方仓库 | `alibaba/MNN` |
| 发布 tag | `3.6.2`，annotated tag |
| tag object SHA | `498882a2781b4a0385e3dcd0042c751cf8708143` |
| **实际源码 commit** | **`7e3c6fb5225d3ccf22807ee641332669df34650d`** |
| Release 发布时间 | `2026-10-29T09:38:22Z` |
| 头文件自报版本 | `include/MNN/MNNDefine.h:75` 起为 `3.6.2` |
| 文档基准 | 同一 commit 下的 `docs/transformers/llm.md`、`docs/compile/engine.md`、`docs/compile/cmake.md` 等；不以 master/latest 替代 |

核查入口：[tag ref](https://api.github.com/repos/alibaba/MNN/git/ref/tags/3.6.2)、[tag 解引用](https://api.github.com/repos/alibaba/MNN/git/tags/498882a2781b4a0385e3dcd0042c751cf8708143)、[官方 Release](https://github.com/alibaba/MNN/releases/tag/3.6.2)。不要将 tag object SHA 当成 checkout 的源码 commit。

`evidence/upstream/` 保存了 **35 份选定文件的原文快照**，不是完整或可构建的 MNN checkout。`evidence/source-manifest.json` 保存路径、官方 URL 和 blob SHA；实际计算的 Git blob SHA-1 全部与 GitHub 返回值一致，另保存 SHA256 于 `evidence/snapshot-verification.json`。这只是源码文件完整性检查，不是编译或推理测试。

## 2. 当前环境：已运行的检查

| 环境项 | 实际结果 | 对最小路径的影响 |
|---|---|---|
| WSL2 | 已枚举到 `Ubuntu`，WSL 版本 2；检查时已启动 | 可使用；最初沙箱内查询被拒绝，扩大只读执行权限后可访问 |
| Ubuntu | `26.04.1 LTS`，`x86_64` | 主机编译环境；不是目标 ABI |
| Git（WSL） | `2.53.0` | 已有 |
| CMake（WSL） | `4.2.3` | 已有，尚未执行 MNN configure，不能宣称兼容已通过 |
| Ninja（WSL） | `1.13.2` | 已有；本报告使用 Ninja，无需依赖 Make |
| g++（WSL） | `15.2.0` | 已有；不能替代 Android NDK Clang |
| Python（WSL） | `3.14.4` | 原生推理不依赖 PyTorch；如自行导出，需另核对 Python wheels |
| Python（Windows） | `3.12.4` | 可处理校验与元数据；不是手机执行环境 |
| Make / 主机 Clang（WSL） | PATH 未找到 | 官方 `build_64.sh` 依赖 Make；本报告的 Ninja 路径不需要它。目标 Clang 应来自 NDK |
| Linux Android NDK | `ANDROID_NDK` / `ANDROID_NDK_HOME` 为空；检查的常用目录未发现 | **构建阻塞项**；未扫描所有磁盘，不能断言其他位置绝无安装 |
| Windows Android SDK | `C:\Users\12761\AppData\Local\Android\Sdk` 已存在；平台 `android-36.1`，build-tools `36.0.0` | SDK 根目录未见 `ndk`、`ndk-bundle`、`cmake`、`cmdline-tools` |
| Windows ADB | `1.0.41`，包版本 `37.0.1-15733141`，绝对路径调用成功 | 已有但未进入当前 PATH，可直接用绝对路径 |
| `adb devices -l` | 最新复查已识别 `ee19377b device`，Windows USB 名称为 Xiaomi 15 | **设备接入阻塞已解除**；系统/ABI/内存/页大小已实际读取，见第11节 |
| WSL ADB / Java / unzip | PATH 未找到 | 使用 Windows ADB 时不需要 WSL ADB；CLI 不需要 Java/Gradle；Linux NDK zip 解压可补 unzip 或使用 Python |
| 可构建源码 / 模型权重 | 工作区起始只有设计文档；本次只保存源码快照及模型小文件 | 需要完整 checkout、完整模型下载与本地哈希校验 |

原始证据见 `evidence/environment/`：`wsl-environment.clean.txt`、`windows-environment.json`、`adb-version.txt`；`adb-devices.txt` 是早期空列表，`adb-devices-latest.txt` 为后续连接成功记录。最新设备原始输出见 `evidence/device/`。WSL 还输出 localhost 代理转发提示，并间歇出现 systemd 用户会话启动提示；本次 Bash 命令能执行。代理提示可能影响后续 WSL 下载，需要以实际网络请求验证，不能据此认定构建或联网已经失败。

重新检查：Windows PowerShell 中运行：

```powershell
wsl -l -v
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate0/check_wsl_environment.sh
$gate0Adb = 'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $gate0Adb version
& $gate0Adb devices -l
```

## 3. 最小方案与依赖选择

使用官方 C++ `llm_demo` 和 `llm_bench`，不构建 Android App。这样可以直接走 MNN C++ 加载、Express、CPU Backend 路径，便于后续源码分析。

建议起始构建组：`arm64-v8a` / `android-21` / `Release` / C++17 / `c++_static` / `MNN_SEP_BUILD=OFF`。LLM、LOW_MEMORY、TRANSFORMER_FUSE、ARM82 开启；OpenCL、Vulkan、QNN、Hexagon、Diffusion、Omni、OpenCV、训练、通用测试关闭。`MNN_SME2=OFF`、`MNN_KLEIDIAI=OFF` 用于减少初始工具链/指令集变量，不涉及修改 Runtime 实现，也不声称这是最高性能配置。

- **必需**：Git、CMake、Ninja、**Linux x86_64 版 Android NDK**、可用的 Windows ADB 与 USB 调试授权、固定 MNN checkout、完整 MNN 模型资产。
- **建议 NDK 起点**：`27.2.12479018`（r27c）。依据是同一提交的 `apps/Android/MnnLlmChat/app/build.gradle:62`，不是 CPU CLI 的源码硬性版本要求。该 App 同时固定 CMake `3.22.1`（第151行）；可作为 CMake 4.2.3 出现兼容问题时的独立回退版本。
- **不必为本路径安装**：Android Studio、Gradle、JDK、CUDA、cuDNN、Qualcomm SDK、PyTorch。完整 Android SDK platforms/build-tools 也不是直接 NDK CLI 交叉编译的必要条件；NDK 自带 sysroot。
- **可选导出依赖**：只有选择自己导出模型时才需要 PyTorch、Transformers、ONNX 等；RTX 4060 Ti 不参与手机 CPU 推理，也不必为 Gate 0 配置 CUDA。

NDK 来自 [Android 官方下载](https://developer.android.com/ndk/downloads/older_releases)，WSL 中解压 Linux 版并设置环境变量。不要将 Windows NDK 的 `windows-x86_64` 工具链当作 WSL 的 Linux NDK。以下假定解压到 `$HOME/Android/android-ndk-r27c`，实际可换成真实路径：

```bash
export ANDROID_NDK="$HOME/Android/android-ndk-r27c"
cat "$ANDROID_NDK/source.properties"
test -f "$ANDROID_NDK/build/cmake/android.toolchain.cmake"
test -x "$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
"$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++" --version
cmake --version
ninja --version
```

NDK 交叉编译参数依据 [Android 官方 CMake 文档](https://developer.android.com/ndk/guides/cmake)：显式传 NDK toolchain、ABI 和 platform。`ANDROID_NATIVE_API_LEVEL` 是 `ANDROID_PLATFORM` 的别名。API 21 沿用 MNN 官方 ARM64 脚本；真机必须不低于构建 API，仍需 ADB 核实。

## 4. 获取源码与构建（以下构建命令尚未执行）

在 WSL Linux 文件系统中放置源码和构建缓存，避免 `/mnt/e` 上大量小文件编译的开销；当前报告保留在 Windows 工作区。

```bash
mkdir -p "$HOME/src"
git clone --depth 1 --branch 3.6.2 https://github.com/alibaba/MNN.git "$HOME/src/MNN-3.6.2"
cd "$HOME/src/MNN-3.6.2"
git checkout --detach 7e3c6fb5225d3ccf22807ee641332669df34650d
git rev-parse HEAD
git rev-parse '3.6.2^{commit}'
git status --short
```

两次 rev-parse 均应为上述完整 commit。保留源码干净状态；无需修改 Schema 或执行 `schema/generate.sh`，官方编译文档将这步列为可选。

已提供 `gate0/build_android_cpu.sh`：检查源码 commit、tracked 文件清洁状态和 Linux NDK，使用全新 build 目录，配置 CPU 路径，仅构建 `llm_demo` / `llm_bench` 目标及其依赖，保存日志和二进制校验信息。脚本完整 CMake 命令可直接审阅。

```bash
export ANDROID_NDK="$HOME/Android/android-ndk-r27c"
bash /mnt/e/DUANCE/gate0/build_android_cpu.sh "$HOME/src/MNN-3.6.2"
```

关键开关的源码依据：

| 开关 | 为什么需要 |
|---|---|
| `MNN_BUILD_LLM=ON` | 根 CMake 第118行起强制启用 LOW_MEMORY 和 TRANSFORMER_FUSE；第906行起 include LLM engine |
| `MNN_LLM_BUILD_DEMO=ON` | engine 第113行起创建 Demo，并在该条件中 include tools；**llm_bench 也受此控制** |
| `MNN_BUILD_BENCHMARK=OFF` | 这是通用 benchmark 的开关，不是 llm_bench 的开关 |
| `MNN_SEP_BUILD=OFF` | engine 使用 OBJECT `llm`，Express 也使用 OBJECT，统一链接进入 `libMNN.so`，减少部署文件 |
| `MNN_BUILD_FOR_ANDROID_COMMAND=ON` | 保持原生 CLI 的构建/输出路径，与 App JNI 构建区分 |
| `MNN_USE_LOGCAT=OFF` | 便于捕获 stdout/stderr；不依赖 logcat 才能看运行日志 |
| `MNN_BUILD_MINI` / `MNN_SKIPBUILD_GEOMETRY` 保持默认 OFF | 不使用仅支持固定 shape 的 MINI 路径，保留 LLM 所需动态形状/Express 功能 |

**不建议原样运行 `project/android/build_64.sh` 作为最小方案。** 该脚本默认启用 `MNN_OPENCL`、Diffusion、OpenCV、IMGCODECS、通用 benchmark 和 tests；没有直接启用 BUILD_LLM；最后调用 `make -j4`，且以当前工作目录的 `../../../` 定位仓库。因此既不等于 CPU-only，也需要目前未找到的 Make。本文改用同一根 CMake 的显式 Ninja 配置，不修改上游脚本。

预期文件（目前均未产出）：

```text
$HOME/src/MNN-3.6.2/build-android-arm64-cpu-gate0/
  llm_demo                    # Android ARM64 ELF 可执行文件
  llm_bench                   # Android ARM64 ELF 可执行文件
  libMNN.so                   # 包含 core / Express / LLM 的共享库
  CMakeCache.txt
  build-environment.txt
  configure.log
  build.log
  cmake-cache-summary.txt
  llm_demo.readelf.txt
  llm_bench.readelf.txt
  libMNN.so.readelf.txt
  binaries.sha256
```

在该 `SEP_BUILD=OFF` / `c++_static` 配置下，不预期额外部署 `libllm.so`、`libMNN_Express.so` 或 `libc++_shared.so`。仍必须以实际 `llvm-readelf -d` 的 NEEDED 项为准；Android 的 `libc.so`、`libm.so` 等由系统提供。若更改为 `c++_shared` 或 SEP_BUILD，须重新核对依赖，不能沿用上述三文件假设。

构建后检查（尚未运行）：

```bash
build_dir="$HOME/src/MNN-3.6.2/build-android-arm64-cpu-gate0"
toolbin="$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
file "$build_dir/llm_demo" "$build_dir/llm_bench" "$build_dir/libMNN.so"
"$toolbin/llvm-readelf" -h -l -d "$build_dir/llm_bench"
"$toolbin/llvm-readelf" -h -l -d "$build_dir/libMNN.so"
```

应看到 AArch64/64-bit ELF、Android 可用的 interpreter/动态库依赖。不要使用主机 `ldd` 来判断 Android ELF 能否在手机运行。

## 5. Qwen3-0.6B 模型资产

最短路径先使用发布者提供的预转换 MNN 模型，减少导出工具依赖：

- 来源：[taobao-mnn/Qwen3-0.6B-MNN](https://huggingface.co/taobao-mnn/Qwen3-0.6B-MNN)。本次通过 Hugging Face API 和固定 revision 的配置/README 实际读取，不依赖搜索摘要。
- 固定 revision：`34dfccda1187ded6e07ea06426da576b0b793c6b`。
- 发布卡声明：Apache-2.0、4-bit 量化。上游 [Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) 模型卡也声明 Apache-2.0。
- 完整导出命令、导出器 commit 和逐层量化参数没有在该模型卡披露，记录为 **unknown/null**，不能反推为“由本次 MNN 3.6.2 导出”。`tie_embeddings` 元数据中的 `8,64` 也不能当作整个模型的完整导出设置。
- 本次**未下载 `llm.mnn`、权重或 tokenizer**，只下载小型配置、README、API 清单；不能声称权重本地 SHA256 校验已通过。

核查到的最小资产：

| 文件 | 远端实际大小 | 说明 |
|---|---:|---|
| `config.json` | 403 B | 已读取；CPU、4线程、low precision/memory |
| `llm_config.json` | 4,880 B | 已读取；28层、hidden_size 1024、Jinja 模板、tie_embeddings 等 |
| `llm.mnn` | 461,520 B | 计算图；未下载 |
| `llm.mnn.weight` | 450,810,338 B | 外部权重；未下载 |
| `tokenizer.txt` | 3,193,569 B | 该发布包的 tokenizer；未下载 |

该发布包没有独立的 `embeddings_bf16.bin`；不要因为新文档列出了该文件就认定资产缺失。Runtime 支持 tied embeddings。新 exporter 生成 `tokenizer.mtok` 并写入配置；旧包使用 `tokenizer.txt`，Runtime 默认也是该名称，并按格式头读取。**保留模型整套配置和文件对应关系，不要只改扩展名，也不要混用不同模型 revision。**

远端 LFS 对象宣告的 SHA256（是下载后的期望值，不是已完成的本地校验）：

```text
llm.mnn
d426c65a5159c938ccc237cdfbd982137f276804f27b414ca0ecf3fc0a660f8c

llm.mnn.weight
953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f
```

`evidence/model/model-lock.json` 保存上述版本、大小、远端 OID 和未知字段。模型卡 README 中的 `MNN_CPU_WEIGHT_DEQUANT_GEMM` 在 3.6.2 根 CMake 第90行起已明确删除；不要复制该旧编译参数。

后续下载示例，在 WSL 执行（本次未执行；约 454 MB，十进制）：

```bash
set -euo pipefail
model_dir=/mnt/e/DUANCE/gate0/assets/Qwen3-0.6B-MNN
revision=34dfccda1187ded6e07ea06426da576b0b793c6b
mkdir -p "$model_dir"
for name in config.json llm_config.json llm.mnn llm.mnn.weight tokenizer.txt README.md; do
  curl --fail --location --retry 2 \
    "https://huggingface.co/taobao-mnn/Qwen3-0.6B-MNN/resolve/$revision/$name" \
    -o "$model_dir/$name"
done
cd "$model_dir"
printf '%s  %s\n' \
  d426c65a5159c938ccc237cdfbd982137f276804f27b414ca0ecf3fc0a660f8c llm.mnn \
  953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f llm.mnn.weight \
  | sha256sum -c -
sha256sum config.json llm_config.json llm.mnn llm.mnn.weight tokenizer.txt > ../model-files.sha256
```

对下载的全部文件检查大小、哈希；使用 Git LFS 时尤其不能把 pointer 文本当权重。SHA 校验只能证明获取的文件与发布对象一致，不能代替 MNN 3.6.2 真机兼容性测试。

为 Demo 建立同目录 `config.cpu.json`，保留源 `config.json`，只固定运行配置（本次未生成，因为完整资产尚未下载）：

```bash
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/mnt/e/DUANCE/gate0/assets/Qwen3-0.6B-MNN')
c=json.loads((p/'config.json').read_text())
c.update(backend_type='cpu', thread_num=4, precision='low', memory='low',
         max_new_tokens=64, sampler_type='greedy', reuse_kv=False,
         async_=False)
c['async']=c.pop('async_')
c['jinja']={'context':{'enable_thinking':False}}
(p/'config.cpu.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
PY
```

**设计方案要求的导出参数追溯仍是未闭环项。** 发布包可用来做最短烟测；若要求完整重建模型的证据，应另建资产组，使用同一 MNN commit 的 `llmexport.py` 与主机版 `MNNConvert` 重导出，记录原始 Qwen revision/哈希、依赖锁、完整参数及所有产物哈希，不覆盖发布包。可核查的候选参数：`--export mnn --quant_bit 4 --quant_block 64 --hqq --mnnconvert <同提交主机版工具> --dst_path <新目录>`；这些参数已在源码中查到，但本次没有执行。完整依赖清单在 `transformers/llm/export/requirements.txt`，未锁版本；不要将 `pip install -r` 成功假定为兼容已通过。当前 WSL Python 3.14 的 Torch/ONNX/MNN wheel 可用性未验证，建议为此另建 Python 3.10/3.11 环境再锁定实际可工作的依赖。Qwen 官方说明 Transformers 低于 4.51.0 不支持该模型。主机 `MNNConvert` 需独立 x86_64 build，不能使用交叉编译的 Android 二进制；优先显式 `--mnnconvert` 避免脚本退回不明版本 PyMNN。

## 6. 手机接入、部署与验证命令（接入/元数据已执行，部署与推理待执行）

小米15现已连接并授权，Windows 设备列表出现 `ee19377b`，状态为 `device`，下面的系统元数据命令已执行。保留接入排查方法供复现：空列表时依次检查数据线/USB口、开发者选项/手机授权、Windows OEM ADB 驱动；`unauthorized` 应在手机授权，`offline` 先处理连接。不要通过 root 或修改系统安全机制解决常规部署。

建议始终使用 **Windows ADB**，不要同时启动 WSL ADB 服务或默认要求 USB passthrough。PowerShell：

```powershell
$gate0Adb = 'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe'
& $gate0Adb devices -l
$gate0Serial = '<从上一步填写真实设备序列号>'
& $gate0Adb -s $gate0Serial shell getprop ro.product.model
& $gate0Adb -s $gate0Serial shell getprop ro.soc.model
& $gate0Adb -s $gate0Serial shell getprop ro.product.cpu.abilist
& $gate0Adb -s $gate0Serial shell getprop ro.build.version.release
& $gate0Adb -s $gate0Serial shell getprop ro.build.version.sdk
& $gate0Adb -s $gate0Serial shell getconf PAGESIZE
& $gate0Adb -s $gate0Serial shell cat /proc/meminfo
```

构建后，在 WSL 将三个文件复制到 Windows 工作区 staging，方便 Windows ADB 读取：

```bash
build_dir="$HOME/src/MNN-3.6.2/build-android-arm64-cpu-gate0"
mkdir -p /mnt/e/DUANCE/gate0/staging
cp "$build_dir/llm_demo" "$build_dir/llm_bench" "$build_dir/libMNN.so" /mnt/e/DUANCE/gate0/staging/
```

PowerShell 部署与烟测。远端目录为新建的专用目录；命令不会清理原手机目录：

```powershell
& $gate0Adb -s $gate0Serial shell mkdir -p /data/local/tmp/mnn-gate0
& $gate0Adb -s $gate0Serial push E:\DUANCE\gate0\staging\llm_demo /data/local/tmp/mnn-gate0/
& $gate0Adb -s $gate0Serial push E:\DUANCE\gate0\staging\llm_bench /data/local/tmp/mnn-gate0/
& $gate0Adb -s $gate0Serial push E:\DUANCE\gate0\staging\libMNN.so /data/local/tmp/mnn-gate0/
& $gate0Adb -s $gate0Serial push E:\DUANCE\gate0\assets\Qwen3-0.6B-MNN /data/local/tmp/mnn-gate0/
& $gate0Adb -s $gate0Serial shell 'chmod 755 /data/local/tmp/mnn-gate0/llm_demo /data/local/tmp/mnn-gate0/llm_bench'
& $gate0Adb -s $gate0Serial shell 'cd /data/local/tmp/mnn-gate0 && LD_LIBRARY_PATH=. ./llm_bench --help' > E:\DUANCE\gate0\staging\llm-bench-help.txt 2>&1
```

每步均记录 `$LASTEXITCODE`；出现失败先停止后续步骤。**`llm_bench --help` 当前只有源码核查证据，没有实际运行输出。** `llm_demo` 不是同一套选项解析器，不能假设它也接受 `--help`；源码 main 显示无参数打印 usage。

创建 UTF-8 无 BOM 的单行 prompt 并跑官方 Demo：

```powershell
[System.IO.File]::WriteAllText('E:\DUANCE\gate0\staging\prompt.txt', "请用一句话介绍北京。`n", [System.Text.UTF8Encoding]::new($false))
& $gate0Adb -s $gate0Serial push E:\DUANCE\gate0\staging\prompt.txt /data/local/tmp/mnn-gate0/
& $gate0Adb -s $gate0Serial shell 'cd /data/local/tmp/mnn-gate0 && LD_LIBRARY_PATH=. ./llm_demo Qwen3-0.6B-MNN/config.cpu.json prompt.txt 64' > E:\DUANCE\gate0\staging\demo.stdout.txt 2> E:\DUANCE\gate0\staging\demo.stderr.txt
$gate0DemoExit = $LASTEXITCODE
$gate0DemoExit | Out-File E:\DUANCE\gate0\staging\demo.exit.txt
```

确认输出是可读且与 prompt 相关的文本，有实际 token 生成、没有初始化或执行报错。该版本 Demo 在 `load()` 失败时可能 `return 0`（第322–325行），因此**退出码为0不够**。本步骤只能证明最小生成可运行，不能代替定量准确率评估。

CPU benchmark 的 Gate 0 冒烟命令（不是 Gate 1 性能基线）：

```powershell
& $gate0Adb -s $gate0Serial shell 'cd /data/local/tmp/mnn-gate0 && LD_LIBRARY_PATH=. ./llm_bench -m Qwen3-0.6B-MNN/config.cpu.json -a cpu -t 4 -p 0 -n 0 -pg 128,64 -rep 1 -c 2 -mmp 0 -qa 0 -fa 1 -load false -j bench-smoke.json' > E:\DUANCE\gate0\staging\bench.stdout.txt 2> E:\DUANCE\gate0\staging\bench.stderr.txt
$gate0BenchExit = $LASTEXITCODE
$gate0BenchExit | Out-File E:\DUANCE\gate0\staging\bench.exit.txt
& $gate0Adb -s $gate0Serial pull /data/local/tmp/mnn-gate0/bench-smoke.json E:\DUANCE\gate0\staging\bench-smoke.json
```

参数语义已经由源码确认，实际运行前仍要核对部署二进制的 help：

- `-p 0 -n 0` 禁止默认 `pp512` / `tg128` 独立测试，只跑指定 `-pg`；省略时会额外运行默认工作负载。
- `-pg 128,64` 让 Decode 使用 Prefill 后的 KV；源码中 `sharedKv=true`，循环调用 `response(tokens,...,64)`。
- `-rep 1` 仍会执行一次不计入结果的 warmup，加一次有效测量；只用于验通，不做收益或稳定性结论。
- Benchmark 使用固定 token id `16` 构造输入，greedy + ignore_eos；**不能用它证明自然语言输出正确性**，所以需要单独 Demo。
- `-c 2` 表示 low precision；`-qa 0` 不量化 KV；`-fa 1` 固定 Attention 模式；均不是权重量化 bit 参数。`-load false` 避免三次加载计时。
- 不在烟测中开 `--profile`。后续如需检查算子回调可单独诊断运行，但不得把诊断时间当正式性能。

CPU 执行证据最低组合：干净 commit + CMakeCache 确认非 CPU 后端关闭 + ARM64 ELF/依赖记录 + 相同二进制哈希 + Demo 实际输出 + bench 请求后端为 cpu 的原始日志和退出码。编译只含 CPU 后端时比“配置写了 cpu”更有约束力；本次这些真机证据尚未产生。若使用含 GPU/NPU 的其他构建，不能只凭请求参数声称实际算子部署。

可选的工具链隔离检查：在导入完整模型前，用 NDK 的 `aarch64-linux-android21-clang++` 编译一个仅打印固定字符串的 C++ 程序，通过同一 ADB 目录执行。它能隔离 ELF/ABI/权限问题，但不计作 MNN 推理成功，本次未运行。

## 7. 主要兼容问题和处理边界

| 现象/风险 | 验证方法与处理 |
|---|---|
| Windows NDK 与 Linux NDK 混用 | 检查 `prebuilt/linux-x86_64/bin/clang++`，不要以主机 g++ 编译 Android ELF |
| CMake 4.2.3 policy 或旧依赖问题 | 先保留真实 configure 错误；必要时换独立 CMake 3.22.1 和全新 build 目录；不要为绕过错误直接改 Runtime。根源码要求3.6、官方编译文档写>=3.10，均不等于4.x已验证 |
| NDK r27 / SME2 汇编 | 原始配置默认 SME2 ON；最小构建显式 OFF，避免初始工具链对新汇编支持成为额外变量；不能据此声称小米15支持/不支持 SME2 |
| `CANNOT LINK EXECUTABLE` / 找不到 so | 检查 NEEDED、`LD_LIBRARY_PATH=.`、所推送库的 ABI 和 SHA；若启用 c++_shared 则另部署同一 NDK 的 libc++_shared.so |
| API / ABI 不匹配、Exec format error | 检查 getprop 的 SDK/abilist 与 readelf；不可推 Linux x86_64 ELF 到手机 |
| 16 KB 页面兼容 | 先 `getconf PAGESIZE`，不能从机型猜测。构建脚本为共享库和可执行文件都加入 max-page-size/common-page-size 16384 链接参数；构建后检查 LOAD/RELRO 并真机运行，不能仅凭参数宣称完全兼容 |
| 权重加载失败/乱码/崩溃 | 检查 LFS pointer、完整文件大小与 SHA、tokenizer 配置、tie_embeddings 和模型目录；不要混用不同导出组的图/权重/配置 |
| 新旧导出参数与模型 README 冲突 | 以本次固定提交为准；`MNN_CPU_WEIGHT_DEQUANT_GEMM` 已删除，`tokenizer.mtok` 不是旧发布包的必需文件 |
| 存储权限 / noexec | 使用 `/data/local/tmp/mnn-gate0` 并 chmod；不从 `/sdcard` 直接执行二进制 |
| OOM / 长时间无输出 | 用短 Prompt、限制64新token，检查 stderr、模型/临时目录和设备可用内存；不可将权重文件大小等同于峰值 RSS |
| USB/ADB 服务冲突 | 固定 Windows ADB；不同时依赖 WSL 内另一 ADB daemon |
| WSL 下载失败 | 单独验证下载 URL 和代理配置；Windows localhost 代理未自动转发到 WSL NAT 时，不能直接假设 WSL 可访问该代理 |

页大小依据：[Android 官方说明](https://developer.android.com/guide/practices/page-sizes)。r28+ 默认16KB对齐，r27及以前需要显式处理；ELF 对齐本身不能证明所有 mmap/运行时代码都符合16KB要求。

## 8. 实际读取的源码入口（均为固定 commit）

以下路径在 `evidence/upstream/` 均有快照。行号为上游一基行号。这里提供 Gate 0 阅读入口，不把静态阅读当成真机已发生的完整调用链或瓶颈结论。

| 路径与位置 | 核查到的作用 |
|---|---|
| `include/MNN/MNNDefine.h:75` | 版本宏3.6.2 |
| `CMakeLists.txt:118`、`:906` | LLM必需特性、include真正engine目录；`transformers/llm/CMakeLists.txt` **不存在**，本次尝试读取返回404，已通过完整仓库tree确认实际目录 |
| `project/android/build_64.sh:1` | ARM64、API21、STL及默认附加构建开关，最后调用Make |
| `transformers/llm/engine/CMakeLists.txt:2`、`:113` | `MNN_LLM_BUILD_DEMO`默认ON，创建Demo并include tools |
| `transformers/llm/engine/tools/CMakeLists.txt:1` | `llm_bench`来自tools/llm_bench.cpp，并链接Profiler.cpp；不是app/llm_benchmark.cpp |
| `transformers/llm/engine/tools/llm_bench.cpp:838`、`:865` | `printUsage`、`parseCmdParams`；支持help、-pg、-rep、-j、--profile等 |
| 同文件 `:1108`、`:1365` | `buildLLM`覆盖采样/后端等配置；shared-KV测量使用合成token、排除首次warmup |
| `transformers/llm/engine/demo/llm_demo.cpp:302`、`:93` | main→createLLM/load→chat或eval/benchmark；支持prompt文件及最大token数 |
| `transformers/llm/engine/src/llm.cpp:41`、`:94`、`:238` | backend_type_convert、createLLM、initRuntime；cpu映射到MNN_FORWARD_CPU，配置线程/精度并createRuntimeManager |
| 同文件 `:337`、`:416`、`:423` | `Llm::load`、外部权重路径、`Module::load` |
| 同文件 `:592`、`:712`、`:1011`、`:1226` | forwardRaw、forward、generate、response的C++入口 |
| `transformers/llm/engine/src/llmconfig.hpp:104`、`:132`、`:195` | 相对模型目录与文件名解析，默认tokenizer.txt、cpu、4线程 |
| `transformers/llm/engine/src/tokenizer/tokenizer.cpp:75` | `Tokenizer::createTokenizer`，支持不同格式头与PIPELINE二进制分支 |
| `express/Executor.cpp:338` | `Executor::RuntimeManager::createRuntimeManager` |
| `express/module/Module.cpp:356`、`:452` | `Module::load`及PipelineModule加载入口 |
| `express/module/PipelineModule.cpp:210`、`:673` | `onForward`和`load`；创建子模块、调度执行 |
| `source/core/Pipeline.cpp:1173`、`:1208` | `Pipeline::execute`与算子`onExecute`调用 |
| `source/backend/cpu/CPUBackend.cpp:789` | `CPUBackend::onCreate`算子实现创建 |
| `source/backend/cpu/CPUAttention.cpp:150`、`:366`、`:1637` | Attention resize/execute与CPU注册；是后续研究入口，尚无真机命中证据 |
| `source/backend/cpu/CPUKVCacheManager.cpp:313`、`:512`、`:730`、`:1027` | KV分配、扩容、清理、更新入口 |
| `source/backend/cpu/arm/CMakeLists.txt:29`、`:40` | AArch64 NEON/低内存汇编收集，以及SME2条件 |
| `transformers/llm/export/llmexport.py:1019` 起 | 量化/转换参数与默认值；不是已执行的导出命令 |
| `transformers/llm/export/utils/model_mapper.py:144` | `regist_qwen3`模型映射支持 |

官方固定版文档：[LLM](https://github.com/alibaba/MNN/blob/7e3c6fb5225d3ccf22807ee641332669df34650d/docs/transformers/llm.md)、[主库/Android 编译](https://github.com/alibaba/MNN/blob/7e3c6fb5225d3ccf22807ee641332669df34650d/docs/compile/engine.md)、[根 CMake](https://github.com/alibaba/MNN/blob/7e3c6fb5225d3ccf22807ee641332669df34650d/CMakeLists.txt)、[llm_bench 源码](https://github.com/alibaba/MNN/blob/7e3c6fb5225d3ccf22807ee641332669df34650d/transformers/llm/engine/tools/llm_bench.cpp)。

## 9. OpenCL / Hexagon / QNN 依赖调查（只调查）

| 路线 | 后续至少需要 | 本次状态 |
|---|---|---|
| OpenCL GPU | 独立构建启用MNN_OPENCL、可访问的厂商OpenCL驱动、模型/算子支持与实际执行验证；Android源码使用动态库wrapper，仓库有OpenCL headers | 未启用、未探测手机驱动、未运行；不要求安装桌面NVIDIA OpenCL/CUDA来代替手机驱动 |
| MNN Hexagon | Hexagon SDK及`HEXAGON_SDK_ROOT`用于编译自定义HTP算子库；`htp-ops-lib/build.sh`匹配DSP架构，得到Android stub与DSP skel；MNN侧MNN_HEXAGON和相应加载路径、针对性模型 | 仅读取README和LLM文档；MNN宿主侧启用后端本身不等于已编译DSP算子；未取得/编译SDK、未验证执行 |
| QNN | QNN/QAIRT SDK头文件与库、QNN_SDK_ROOT、对应Stub/Skel/System等库；LLM离线转换还需x86_64 Linux工具链与专用产物，在线/离线路径分开 | 仅读取QNN CMake和官方文档；未启用、未生成专用模型 |

Hexagon直接后端和QNN是不同构建/模型路线。不能从Snapdragon 8 Elite型号推出可访问NPU或算子实际跑在NPU。LLM文档与通用NPU文档的插件/后端选择规则也不能混用。例如QNN离线Plugin可在CPU Backend内封装QNN执行；这不适用于本次关闭插件/NPU的CPU路径。

## 10. 当前验收状态与下一步顺序

- [x] 阅读设计方案，只开展Gate 0。
- [x] 核查tag→精确commit、真实版本宏、构建入口与官方固定版文档。
- [x] 实际探测WSL与Windows ADB；保存原始证据。
- [x] 核查模型来源、revision、许可声明、资产清单与远端哈希；未知导出参数写null。
- [x] 提供最小CPU构建脚本、预期产物、部署和验证命令。
- [x] 两个Bash脚本的`bash -n`语法检查无错误；**只验证语法**。
- [ ] 安装/定位Linux NDK并验证版本与目标Clang。
- [ ] 获取完整干净MNN checkout，实际configure和编译通过。
- [ ] 下载模型并执行本地完整性校验，补齐/明确导出来源边界。
- [x] ADB识别并授权小米15，实际采集设备元数据，全部14项只读shell查询退出码为0。
- [ ] 真机执行help、Demo文本生成与CPU bench smoke，保留全部日志、退出码和二进制/模型哈希。

建议顺序：**定位Linux NDK → 构建ARM64 CLI → 下载校验模型 → Demo生成 → 单次CPU bench烟测 → 验收Gate 0**。Windows ADB接入已完成；其余条件完成前，不进入Gate 1测速结论或任何Runtime优化。

## 11. 最新真机接入证据

本节替代前期“设备未枚举”的连接状态。采集时间：`2026-11-08T13:21:11Z`（UTC；America/Los_Angeles 当地同日）。

| 项目 | 实际读取结果 |
|---|---|
| Windows USB设备 | `Xiaomi 15`，驱动状态 `OK / CM_PROB_NONE` |
| ADB序列号/状态 | `ee19377b` / `device` |
| Android型号/产品 | `24129PN74C` / `dada` |
| SoC / 厂商 / hardware | `SM8750` / `QTI` / `qcom` |
| Android / API | `16` / `36` |
| 系统版本标识 | `OS3.0.307.0.WOCCNXM`，完整fingerprint保存在原始记录 |
| ABI / 内核架构 | `arm64-v8a` / `aarch64` |
| 页大小 | `4096` 字节（4 KiB）；当前设备不是16 KiB页面配置 |
| `/proc/meminfo` MemTotal | `15476168 kB`，约 `14.76 GiB`；是内核报告可管理内存，不是模型RSS |
| 采集时 MemAvailable | `8351600 kB`，约 `7.96 GiB`；只代表该时刻，不保证推理时可用量 |
| shell身份 | `uid=2000(shell)`，SELinux上下文 `u:r:shell:s0` |

记录于 `evidence/device/device-metadata.json`，包含每条命令、原始输出和退出码；各项文本另存为同目录文件。14项只读shell查询均退出0，仅证明元数据读取成功。本次没有推送模型/可执行文件，没有运行MNN Demo、help或benchmark。API 36与ARM64满足候选API 21/arm64构建的版本和ABI条件，但不代替ELF链接与模型执行验证。NDK、实际编译、完整模型资产和推理结果仍待闭环，**Gate 0整体仍未通过**。
