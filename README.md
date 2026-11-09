# MNN Android LLM Runtime

在小米 15 上运行 Qwen3-0.6B，并跟进到 MNN 的 C++ 执行层，分析一个 Token 从生成到计算完成经过了哪些环节。

这个项目里，我完成了 CPU / OpenCL 的构建部署，编写了真机测试、执行追踪和数值对照工具。除了跑出吞吐数据，我更关心两个问题：时间实际花在哪里，以及不同后端的计算结果为什么不同。

开发环境是 Windows + WSL2，目标设备是 Snapdragon 8 Elite / Adreno 830。使用 MNN 3.6.2、Android NDK r27c，模型和源码版本固定。

## 主要实现

### 真机部署与自动化测试

从源码交叉编译 Android ARM64 版本，通过 ADB 部署模型和可执行文件。我把重复的测试步骤做成了脚本：安排 CPU/GPU 交错运行、等待设备冷却、收集吞吐和进程内存，并将每次命令、输出、退出码及设备状态放进独立目录。

这套工具完成了 50 次 CPU 基线测试，以及最后一轮 36 次 CPU/GPU 对照。拿到一个异常数据点时，可以回到对应进程的日志，而不必重新猜测当时用了什么配置。

代码入口：[ARM64 构建](gate0/build_android_cpu.sh) · [OpenCL 构建](gate2c-opencl/scripts/build_opencl.sh) · [CPU/GPU 测试脚本](gate2d-comparison/scripts/run.py)

### Decode 执行追踪

我沿着生成循环追到 Attention 和 KV Cache 管理，添加了逐 Token 的耗时、上下文长度和扩容事件采集。追踪记录先写入内存，运行结束后统一导出，避免每个 Token 都打印日志。

结合已有算子 Profiler，我把 Decode 的主要开销定位到量化线性投影，并将运行节点映射回 C++ 执行器。长生成中的 Attention 成本增长和局部 KV 扩容尖峰，也可以在时间线上对应起来。诊断补丁放在独立分支，性能测试仍使用原版库。

代码入口：[追踪实现与补丁](gate2-decode/README.md) · [热点分析](gate2b-decode-hotspots/Gate2B_Decode热点归因报告.md)

### CPU/GPU 数值对照

CPU 和 GPU 能生成文本之后，我继续排查了两端 Logits 的差异。通过隔离第一层 Q 投影、采集实际输入和量化参数，编写了不依赖 MNN 计算函数的主机参照程序，重建整数点积和浮点后处理。

最终在两个固定输入、共 43,008 个输出元素上，独立复算结果与 CPU Low 路径逐字节一致。这个过程也定位出一处容易忽略的细节：ARM Kernel 的单 Token 尾部采用不同的 FMA 运算顺序，参照程序需要按实际路径实现。

代码入口：[C++ 独立参照](gate2c3-quant/scripts/reference.cpp) · [权重解析](gate2c3-quant/scripts/decode_weight.py) · [数值验证报告](gate2c3-quant/Gate2C3_动态量化数值验证报告.md)

## CPU 与 GPU 的表现

下面是同一轮测试的中位吞吐，单位 tok/s，每个后端、每组负载各运行 6 个独立进程。

|输入 / 生成 Token|CPU Prefill|GPU Prefill|CPU Decode|GPU Decode|
|---|---:|---:|---:|---:|
|32 / 64|368.15|472.06|96.38|69.97|
|128 / 64|346.63|1015.44|93.35|71.03|
|128 / 256|339.97|1014.73|89.73|67.50|

这台设备上，GPU 处理整段输入更快，CPU 逐 Token 生成更快。`128 / 64` 两段计时相加后的结果比较接近，配对测试中两端都出现过领先。具体范围和设备状态见[性能对照报告](gate2d-comparison/Gate2D_CPU_GPU性能对照报告.md)；表中是 Benchmark 阶段吞吐，不是完整请求延迟。

OpenCL 执行由设备 Kernel 事件确认，相关记录见[GPU 执行验证](gate2c-opencl/Gate2C_OpenCL可行性报告.md)。

## 任务评估

我还编写了 100 条分类、JSON 抽取、指令和短问答用例，以及对应的确定性评分程序。当前模型配置的成功率为 CPU 24%、GPU 25%，没有达到预设的应用要求。失败包含格式遵循和内容错误，详细用例保留在[质量评估报告](gate2c4-quality/Gate2C4_模型质量验收报告.md)中。

因此，上面的性能结果用于了解后端执行特点；如果要用于实际应用，还需要单独解决模型和任务适配问题。

## 从哪里开始

只看代码，建议先读这三个入口：

- [Benchmark 运行与统计](gate2d-comparison/README.md)：如何组织实验、保存结果和计算对照数据。
- [Decode 追踪](gate2-decode/README.md)：C++ 采集点、补丁、逐 Token 原始记录。
- [量化独立复算](gate2c3-quant/README.md)：输入、权重解析、参照程序和误差对照。

本地安装 Python 3.12 后，可以先运行不依赖手机的检查：

```powershell
python -B gate2d-comparison/scripts/test_analysis.py
python -B gate2c4-quality/scripts/test_score.py
python -B verify_project.py --available
```

重新构建和真机运行，请参考 [CPU 部署说明](gate0/Gate0_执行报告.md)和 [OpenCL 构建说明](gate2c-opencl/Gate2C_OpenCL可行性报告.md)。仓库保留代码、报告、原始结果和归档二进制；模型大权重及 NDK 安装包不随 Git 上传，版本和获取入口见[归档说明](publication/README.md)。

完整项目说明见 [FINAL_TECHNICAL_REPORT.md](FINAL_TECHNICAL_REPORT.md)。各阶段目录保留详细报告，实验已结束；本次 GitHub 整理只更新项目展示文档。
