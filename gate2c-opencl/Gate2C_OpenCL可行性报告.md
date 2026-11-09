# Gate 2-C0/C1｜MNN Android OpenCL可行性报告

**小米15可以运行固定版本MNN OpenCL，现有Qwen3-0.6B确实在Adreno GPU上执行主要模型计算并生成可读中文。两个小输入的Logits初筛未达到预先设定的探索性阈值，因此不宣称完整精度兼容通过；暂缓GPU性能基线，建议先进入GPU数值正确性与执行路径研究。**

本轮未优化Runtime、未测试GPU性能收益、未运行NPU、未启动第二个项目。报告生成UTC：2026-11-08T20:15:25.426624+00:00。

## 1. 验收结论及边界

|问题|实际结论|证据|
|---|---|---|
|OpenCL驱动/设备可用？|C0通过：库可访问、GPU枚举成功、独立算术kernel正确|results/probe-*；普通shell uid2000|
|固定MNN可构建？|clean与事件诊断版均configure/build退出0|两个全新build目录，各625步；ELF/依赖/哈希齐全|
|现有模型可执行？|C1加载/文本生成烟测通过，21输入+16输出|clean和profile各1次成功，完整stdout/stderr/exit|
|是否真实GPU计算？|主要线性层与Prefill/Decode Attention有设备事件证据|Convolution、flash_attention_prefill/partial/reduce数量与模型前向一致|
|CPU回退？|未见启用后的Creator回退日志；不声称整个进程无CPU工作|诊断编译宏已核对；Tokenizer/采样/shape管理仍可在CPU|
|CPU/GPU精度一致？|尚未通过本轮Logits数值初筛|两个输入全finite/shape一致/Top1相同，但误差阈值未过|
|是否进入GPU性能基线？|暂缓；先查数值差异，再决定正式门禁|不把可读文本或运行成功替代精度检查|
|NPU兼容？|仅静态调查，未验证设备NPU可运行|模型与文档推荐组合不同，SDK/产物尚未准备；源码支持面也有文档差异|

初筛阈值不是MNN官方精度规范；未达阈值既不能被“文本看起来正常”覆盖，也不等于已经证明GPU kernel存在Bug。

## 2. 固定版本、环境与隔离

- MNN3.6.2 commit `7e3c6fb5225d3ccf22807ee641332669df34650d`；源码 `/home/shawrange/src/MNN-3.6.2` tracked工作树保持干净，Gate2-A诊断分支未动。
- 模型revision `34dfccda1187ded6e07ea06426da576b0b793c6b`，权重SHA256 `953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`；本轮未重导出或改权重/图。
- Windows + WSL Ubuntu，Linux NDK r27c/Clang18.0.3，CMake4.2.3/Ninja1.13.2；小米15 SM8750、Android16/API36、arm64-v8a、设备页4KiB、shell uid2000，SELinux权限未调整。
- 预先对Gate0/1/2-A/2-B共5756个原文件建立保护哈希；最终完整性核对见 `verification-summary.json`。没有覆盖CPU lib/CLI、旧构建目录或原始实验文件。
- 新build目录为 `build-android-arm64-opencl-gate2c` 与 `...-profile`；新手机根目录 `/data/local/tmp/mnn-gate2c-20261108`，clean/profile/oracle各自子目录隔离；tuning cache在新工作目录内。

## 3. 固定源码机制与OpenCL参数

详细文件、函数、行号见[后端选择与源码入口](后端选择机制与源码入口.md)。45份关键源码快照均对应固定提交；没有以master的新接口替代。

- root CMake的MNN_OPENCL及后端CMake决定注册、Buffer/Image构建和动态wrapper；Android使用仓库OpenCL头文件及dlopen，不需在本机额外安装OpenCL SDK。
- `OpenCLWrapper.cpp:39–54,171–180`加载libOpenCL候选；`OpenCLRuntime.cpp:52–85`选择第0个platform及GPU device，读取名称/driver并建立context/queue。
- `llm.cpp:41–60`把opencl映射为3；`:237–271`创建Runtime。`llm_bench.cpp:1145–1150`传入-t请求，LLM在`:243–247`自动OR 64和512。
- 因此本轮请求thread_num=4，**有效GPU模式580=Wide tuning(4)|Buffer(64)|RecordBatch请求(512)**。-t不是GPU线程数量；没有使用“GPU四线程”表述。CPU oracle始终是4线程。是否实际启用录制还依赖driver能力；诊断宏会改变提交/等待方式。
- `Schedule.cpp:111–155`可能后端级回退；`Session.cpp:31–59`建立CPU backup；`Pipeline.cpp:589–600`在主execution创建失败时尝试backup；`OpenCLBackend.cpp:674–779`按类型/内存模式/数据类型/尺寸/creator支持决定是否返回nullptr。
- `MNN_GPU_TIME_PROFILE=ON`启用设备事件；它与`llm_bench --profile`的host op callback不是同一个观测层。本轮主要使用前者证明GPU落点；`llm_bench --help`实际输出也保存，但没有跑GPU性能基线或重复benchmark矩阵。

## 4. 手机OpenCL环境实查

普通ADB可访问 `/vendor/lib64/libOpenCL.so` 和 `libOpenCL_adreno.so`；`libOpenCL.so`也在设备vendor public.libraries列表中。`/system/lib64/libOpenCL.so`不存在，其原始ls错误已保存；这没有被误判成设备不支持。

独立 `cl_probe` 用dlopen/dlsym枚举并在GPU queue执行 `b[i]=2*a[i]+1`，16元素全部正确、event状态CL_COMPLETE、START/END查询成功。裸名字与vendor绝对路径两种加载均退出0；裸名字解析到 `/vendor/lib64/libOpenCL.so`。这只证明驱动小kernel，LLM证据另见第6节。

|项目|实际读取值|
|---|---|
|Platform|QUALCOMM Snapdragon(TM)，FULL_PROFILE，OpenCL3.0 QUALCOMM build0800.71|
|Device|QUALCOMM Adreno(TM) 830；CL_DEVICE_TYPE_GPU=4|
|Driver|OpenCL3.0 QUALCOMM build0800.71 Compiler E031.47.18.49|
|OpenCL C|OpenCL C3.0 Adreno830；本探针用-cl-std=CL1.2编译成功|
|Global memory|7923798016 bytes（驱动报告，不是本应用可用保证）|
|Max single allocation|1073741824 bytes|
|Local memory / Max WGS / compute units|32768 bytes / 1024 / 12|
|Image / SVM|Image支持；SVM capabilities=11，查询退出0|
|相关扩展|cl_khr_fp16、cl_khr_subgroups、cl_qcom_recordable_queues等；完整列表见raw|

动态依赖：新libMNN的NEEDED为liblog/libm/libandroid/libdl/libc；没有NEEDED libOpenCL是wrapper动态加载设计。拉取的vendor两库只读ELF检查保存在 `evidence/driver-elf/`；例如adreno库依赖libcutils、libvndksupport、liblog、libc++、libc/libm/libdl。没有把vendor库复制进新运行目录替换系统driver。

Android兼容边界：此次证明shell CLI域可用，不自动证明APK linker namespace/manifest/ABI/厂商库暴露均已通过；设备实际4KiB页，产物LOAD alignment0x4000兼顾16KiB，但未测试另一台16KiB设备。其他驱动、单进程GPU内存限制、长上下文峰值分配、cache格式/权限都未由小烟测排除。失败应保留dlerror/CL错误/编译日志，不绕过权限。

## 5. 独立构建与CPU选项差异

两个构建都基于干净固定源码、Release/C++17、Android21、c++_static、SEP_BUILD OFF、LLM/LOW_MEMORY/TRANSFORMER_FUSE/ARM82 ON，SME2/KleidiAI/GPU其他后端/QNN/Hexagon OFF。

|选项|归档CPU|OpenCL clean|OpenCL诊断|
|---|---|---|---|
|MNN_OPENCL|OFF|ON|ON|
|MNN_OPENCL_SIZE_CUT|未配置/不构建该后端|OFF，保留Buffer|OFF|
|MNN_GPU_TIME_PROFILE|OFF|OFF|ON|
|CMAKE_CXX_FLAGS|空|空|-DOPENCL_FALLBACK_LOG|
|源码修改|无|无|无，仅启用既有条件日志/事件代码|

全部configure/build exit0，每份625个Ninja步骤。CMake弃用及上游编译warning保留，未修改源码来消除warning。实际configure.command、build.log、CMakeCache、ninja-commands、readelf和与CPU cache的逐项差异在 `evidence/build/{clean,profile}/`；路径/缓存目录差异与功能选项差异分开可核查。

|产物|SHA256|
|---|---|
|clean libMNN.so|4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61|
|profile libMNN.so|6a48f53e98de0e9e343346d36e98d01596fea2dfc10f6a4eca616cbab262536d|
|两份llm_demo（与CPU CLI相同）|37e65f0a8881699ec22bc96dd3ec2457c00ec3699ff2e4a7ef810ca8b1b915d9|
|两份llm_bench（与CPU CLI相同）|fd85bf65a75656d023feb9e2ad315f6ee7c6033c8f1591a835e54d2985db4676|

CLI相同不表示后端相同：新libMNN包含OpenCL，运行日志保存每次显式LD_LIBRARY_PATH及手机端哈希。ELF均AArch64/Android PIE或共享库，所需系统库与解释器检查齐全。

## 6. 模型烟测、实际GPU落点与回退边界

固定模型属性已在Gate2-B核对，本轮再做NPU静态解析：196个4bit线性层、1个8bit词表头，共197个Convolution；28个Attention。clean请求Low precision/memory、power normal、greedy、mmap=false、async=false、thread_num4（GPU模式580）；未重新量化。当前自然问题为“请用中文简短解释什么是人工智能。”，Qwen3关闭thinking，21输入Token、16生成Token。

clean成功run：`results\clean-20261108T195442Z-58415b`；profile成功run：`results\profile-20261108T195615Z-85267b`。均exit0，stderr无模型错误，clean可读输出为：

> 人工智能（AI）是一种通过计算技术实现高效、智能的解决问题的系统

16 Token上限导致句尾未必完整。profile日志会与逐kernel打印交错，不拿它的文字连续性作性能或质量结论。

### 设备执行事件

|实际事件标签|计数|与模型关系|
|---|---|---|
|Convolution0|3349|197 × (1 Prefill + 16 Decode)|
|flash_attention_prefill|28|28层 × 1 Prefill|
|flash_decode_partial|448|28层 × 16 Decode|
|flash_decode_reduce|448|28层 × 16 Decode|
|rearrange_k / rearrange_v|28 / 28|Prefill KV整理各28次|

全部事件总数21654，上述关键事件均为非零时间。事件来自实际OpenCL enqueue、wait和CL_PROFILING_COMMAND_START/END，`onExecuteBegin`会清掉前次事件，数量与真实forward吻合；这是LLM线性/Attention执行的证据，不只是初始化、驱动枚举或权重上传。Convolution0是Runtime事件标签，未冒充具体kernel函数名；Attention标签则可直接对应buildKernel和enqueue源码。

本轮启用OPENCL_FALLBACK_LOG且核对实际编译命令，**回退日志0行**。主要线性层和Attention的事件数量完整，证明并非LLM全程静默CPU执行。但没有建立每一个execution的CPU占比计数；CPU仍进行Tokenizer、采样、shape/常量和管理工作，因此不宣称“进程100%都在GPU”或完全无CPU路径。

诊断构建绕过部分record-queue分支、增加事件等待/打印，与clean的提交策略不完全相同；它确认同源码支持的模型计算路径，不用来精确量化clean时间份额。raw中的秒数/TPS含首次kernel编译、tuning/cache等，不是可信GPU性能基线，也未与CPU作速度收益比较。

### 首次配置错误，明确不计通过

`results\clean-20261108T195334Z-f03f9d` 中脚本初版把模型/tokenizer字段设为绝对路径，该版本LlmConfig直接拼接base_dir，得到`.//data/...`，打印tokenizer file not found/LLM init error，虽exit0但没有实际输出。`analysis/summary.json`及该run的runtime-analysis明确semantic_success=false。原stdout/stderr/exit/初版runner未改写。

仅修正新配置：base_dir指向已有固定模型目录，文件字段用相对名，随后完整重跑成功；没有修改Runtime或旧模型。第一次cache不存在的Load Cache file error与模型初始化错误分开识别。当前脚本同时检查错误标记，分析再检查实际生成Token，不能只依退出码。

## 7. Logits接口、实际数值初筛与阻塞点

在数值运行前已写下[GPU正确性对照计划](GPU正确性对照计划.md)，包括固定阈值。本轮用public `response(ids,...,0)` 与 `getOutputs()[0]->readMap<float>()`，在CPU归档库与新clean OpenCL库间运行同一小驱动。两种输入分别为8个重复token16、13 Token的自然语言模板输入；各只做Prefill，共4次小运行，没有Decode精度矩阵或大规模性能测量。

两后端input IDs完全相同，shape均 `[1,1,151936]`、host dtype float32、全部finite，完整logits和配置/退出码保存，证明能得到可靠可核对的数值对象。判据：relative RMSE<=0.02、cosine>=0.999、满足abs误差<=0.1+0.02×abs(CPU)的元素比例>=99.9%，shape/finite同时通过；不是要求逐字节相同。

|输入|logits元素|相对RMSE|cosine|abs/rel界内比例|最大绝对误差|平均绝对误差|Top1相同|Top5重叠|初筛|
|---|---|---|---|---|---|---|---|---|---|
|synthetic|151936|0.066799|0.997819|47.30%|1.396118|0.206018|True|4/5|未通过|
|natural|151936|0.114356|0.993942|24.96%|3.386719|0.567305|True|4/5|未通过|

**两例均未通过，阈值未放宽。** Top1相同只说明这两处最大logit排序没有改变，不能替代整体误差判据。数据来自 `results\logits-20261108T195947Z-5aba2f`，分析为 `analysis/logits-comparison.json`，原始float32 LE文件可重新计算。

目前阻塞是**数值兼容性尚未确认**，不是已观察到的驱动无法加载、构建失败或模型解析失败。CPU输入动态量化、GPU低精度/反量化与累加顺序、个别算子误差或提取/状态边界都是待核查方向；本轮没有逐层定位，不能断言偏差全属正常浮点误差，也不能直接定性Runtime Bug。

后续按计划做固定上下文teacher forcing、分精度配置、层级输出定位与较多固定语料，避免自由生成分叉后比较不同上下文。正确性门禁明确前，不建立性能收益结论，不实施kernel/Runtime优化。

## 8. Hexagon/QNN静态可行性

完整调查见[Hexagon与QNN静态调查](Hexagon与QNN静态调查.md)。重要结论：

- 直接Hexagon依赖自定义host stub/DSP skeleton/FastRPC及Hexagon SDK工具链；QNN调用QNN SDK graph接口，两者不是同一后端。QNN online构图与offline bin/Plugin转换部署也不同，offline Plugin在CPU登记不能凭配置CPU判断执行硬件。
- 同提交文档列8 Elite为SOC69、DSP arch79；这是静态文档映射，未运行NPU查询或权限验证。
- 当前模型197个量化层按loader规则均asymmetric，28个Attention output_c4=false，且词表头8bit，不匹配Hexagon LLM文档的4bit对称/C4推荐组合。
- **文档/代码有支持面差异**：实际HexagonConvolution已包含W8与部分block-asymmetric分支，Attention又有实际layout/dtype检查。因此不能仅凭旧推荐组合就宣布整个Runtime绝对不支持；当前模型能否满足完整布局/shape/执行契约仍待验证。QNN现模型未转换/校准/构图，不声明直接兼容。
- 本WSL会话QNN_SDK_ROOT/QNN_ROOT/HEXAGON_SDK_ROOT均未配置，默认自定义HTP输出目录不存在；仅核查已知位置，不声称全盘无SDK。后续需验证include/QNN、host转换工具、v79 Stub/Skel及runtime库、校准与新模型资产，不能靠改backend字符串替代。
- 未下载/构建DSP自定义算子，未进行任何NPU运行或性能测试。OpenCL已可用，不需为了让本阶段“成功”而切换NPU或绕过权限。

## 9. 下一阶段明确判断

**值得继续GPU深入研究，优先主题是CPU/GPU数值差异定位和精度门禁；暂不把这份模型/模式用于可信CPU/GPU性能比较。**

可优先追踪 `ConvBufLowMemoryExecution` 的权重路径/精度与CPU动态输入量化差异，接着用Norm、QKV、Attention、MLP、词表头层级结果定位误差首次放大处。Device/runtime加载与Buffer/record队列、GPU KV机制也有真实源码及事件入口可研究；本轮不进行改进或性能调参。

只有数值判据、固定输入/状态、实际GPU落点与回退边界都清楚后，下一阶段再建独立GPU基线，区分首次编译/tuning和稳定执行，保留CPU作为oracle与对照。NPU维持静态候选，不自动启动。

## 10. 交付与复现

[README](README.md)列明构建/部署/分析命令、独立目录和所有原始产物。`scripts/analyze.py`从raw输出提取事件数量和语义成功状态；`compare_logits.py`从原始f32重算指标，阈值不依结果调整；`verify.py`核对源码、旧证据、CPU/GPU设备资产及交付链接，`artifact-manifest.sha256.json`锁定本目录产物。

原会话protocol.json复用了Gate1配置容器，保留了未使用的CPU/workloads/warmup字段；它们不是本轮执行参数，以每run实际command/config.opencl.json为准。`experiment-config.json`明确本轮真实负载和GPU编码，旧记录未改；当前runner已去除无关字段。没有把继承标签用作GPU执行证明。

`verification-summary.json`区分delivery integrity与C1数值结果：交付完整性可通过，同时numerical_screening仍为false。不得把前者转述成完整GPU精度验证已通过。
