# Gate2C3｜CPU动态输入量化路径独立数值验证报告

**判断A：本轮证据支持预期量化误差，不建议修改Runtime。** 对固定第一层Q投影，独立主机程序重建的INT8输入、scale和权重语义与实际采集一致；按真实ARMV86整数GEMM、FP32后处理和FP16输出顺序复算，两个输入的全部43,008个输出元素与归档CPU Memory_Low逐字节一致。观察到的约1%–2%浮点参照差异由该量化计算契约复现，无需制造Backend Bug。

此处43,008是两个输入的输出元素数，不是独立请求数。只使用2种固定输入（8/13 Token），10个配置/进程尝试均成功，每进程3次单Q执行。已停止此算子的进一步正确性定位；下一阶段应是独立模型质量验收，本轮没有启动全模型评测、GPU正式性能基线、NPU或任何性能优化。

## 1. 固定环境与隔离

MNN3.6.2，基准commit `7e3c6fb5225d3ccf22807ee641332669df34650d`。Qwen3-0.6B-MNN revision `34dfccda1187ded6e07ea06426da576b0b793c6b`，模型图/权重未修改或重新量化。小米15/SM8750、Android16；普通ADB shell。Windows/WSL Ubuntu/NDK r27c，主机独立参照使用已有g++/NumPy，环境原始记录见[evidence/environment](evidence/environment/host.json)。

CPU归档库SHA256 `47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e`；GPU沿用C2固定clean OpenCL库 `4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61`。模型权重SHA256 `953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`。手机部署新目录，每次运行保存命令、stdout、stderr、退出码、前后设备状态与哈希。

新worktree `/home/shawrange/src/MNN-quant-gate2c3`，分支 `feature/quant-gate2c3-diagnostic`，基于固定commit加未提交的明确诊断补丁。仅新增buffer采集helper和执行器采集点，无数学表达式、Kernel或调度修改。补丁[diagnostic.patch](evidence/diagnostic.patch)可在固定干净源码上apply --check，原始基准源码保持tracked clean。C2、CPU基线及此前共8,971文件保护快照在开始时生成，最终逐个核验，见[verification-summary.json](verification-summary.json)。

诊断CPU库SHA256 `217d09f705d640b0a6286df12e7111deb9746222f59a70d37c6eb927f7f8a316`。独立构建454个Ninja步骤，configure/build均退出0。与原CPU功能选项相同，新增`-DMNN_GATEC3_CAPTURE=1`；从GPU脚本生成时保留的MNN_OPENCL_SIZE_CUT在CPU构建不使用，其CMake warning保留，不被当作有效选项。库/配置/ELF/日志见evidence/build。为剥离符号库补生成link map，重链接字节哈希不变；实际函数地址由同一哈希库与map对应。

## 2. 精确计算契约及实际路径

完整公式、真实函数和固定源码行号见[精确计算契约与源码位置](精确计算契约与源码位置.md)。关键事实：

- CPU Low物理输入FP16/NC8；每Token的全部1024通道一组，输入对称INT8 zero-point=0。不是按权重64通道组分别求输入scale。实测dynamicOption0、inputBlockNum1、useBatchQuan=true、im2colBasedInt8=true，量化helper一次调用且availableThreads1。
- 先对FP16输入取absmax，再用FP32除法求Q=127/max、D=max/127；Q再转FP16，与输入作FP16乘法。FCVTAS按最近整数、半值远离零取整，SQXTN饱和到[-128,127]。因此直接用FP32乘127/max、np.rint或普通截断都不是本路径的精确参照。
- 权重INT4按每输出通道、每64输入通道分块，16组；原alpha是FP32 `[offset,scale]`。原文件header22字节，nibble高位先；signed权重[-8,7]。实际ARM GEMM读取unsigned nibble[0,15]，使用prepared offset `offset−8*scale`抵消平移。
- INT32分块点积后，FP32权重scale、输入D、srcKernelSum修正及FMA；块间FP32累加。Bias为隐式正零。最终RN到FP16并夹紧实测[-65504,+65504]；本轮没有输出达到夹紧阈值，也没有ReLU等额外激活。
- 实际mGemmKernel地址映射到`MNNGemmInt8AddBiasScale_ARMV86_w4_Unit_FP16`；helper映射到FP16 AbsMax/QuantScale/DynamicQuant与ARM86 SumByAxis。不是根据芯片型号猜测路径。weightQuantInfoMode0，未走FP16磁盘alpha/紧凑metadata。

特别是**单Token尾部TILE_1的FMA顺序与TILE_10/8/2不同**。13 Token的最后位置采用`scaleEff=RN32(s*D)`，再对running accumulator做两次FMA；独立程序必须按该分支复现。具体汇编入口与行号、指针ELF偏移见契约文档和analysis/results.json。

## 3. 原始证据与输入生命周期

复用C2已验证的两份q_input及相同权重，原图Tensor Path只保留第一层q_proj和必要Raster布局转换；没有Attention/KV、其他层或采样。主会话 `results\q-only-20261109T070717Z-360e22`。

每次执行前重新上传输入。Tracing在**DenseConvInt8TiledExecutor::onExecute真实入口**及量化后采集，而不只依赖before callback。两种输入的r0首次执行、r1/r2后续执行全部入口与源逐字节一致；每次量化前buffer、INT8、Q/D scale也全部与主机独立重建一致。CPU浮点和GPU对照仅将入口回读一致的r1/r2用于误差归因；GPU首次before回调仍可能处于物化前，未据此解释Kernel消费内容。没有复用C2早期失效的隔离会话。

|输入|输入Token位置数|INT8范围|Q scale范围|D scale范围|整数block dot范围|
|---|---|---|---|---|---|
|synthetic|8|[-127,113]|[56.83916091918945, 56.83916091918945]|[0.0175935048609972, 0.0175935048609972]|[-2682, 2106]|
|natural|13|[-127,127]|[15.408531188964844, 69.39594268798828]|[0.014410063624382019, 0.06489911675453186]|[-4730, 5099]|


原始量化前FP16 buffer、canonical输入、INT8 buffer、absmax、Q/D、zero等元数据、实际packed权重与metadata、输出、Bias及夹紧参数均保存于每个diag-on的out/trace.*。原权重段、alpha和公开FlatBuffer元数据独立保存在evidence/weight；与Runtime loader未重排字节精确核对，prepared scale/offset也全部精确一致。source输入与本轮元数据有完整哈希链。

所有3次执行的归档CPU Low、同诊断库Tracing OFF、ON输出逐字节相同；同配置三次输出也相同。这里没有把多次重复或多个Token当作独立语料样本。

## 4. 独立参照的实现

A：`decode_weight.py`仅用struct/NumPy解析原权重header、sample表和nibble，得到signed INT4、原FP32 scale/offset和零Bias。标准C++程序用FP64计算`x × (qSigned*scale+offset) + bias`。A仍是**同一量化权重**的高精度辅助参照，不是原始未量化模型黄金输出。

B：标准C++程序独立重建Q、D和整数输入，INT32计算每64通道块dot，按实测metadata mode0及ARMV86各tile执行FP32乘法/FMA、累加、Bias与FP16夹紧。程序不调用MNN量化、解码或GEMM函数，也不链接libMNN；g++ `-ffp-contract=off`，需要融合的位置显式std::fma，检查Host最近偶数舍入环境。独立dot/sum文件保留，便于逐块复核。

另外保存B64_ideal（同一重建INT8/D与原反量化权重，FP64数学表达式）和B32_prehalf（真实FP32后处理、输出转half前），分开观察输入量化与输出舍入。没有将不同来源误差简单线性相加或计算虚假的误差占比。

## 5. 数值对照结果

rRMSE=`sqrt(sum((b−a)^2)/sum(a^2))`，Cosine用向量内积定义；每行以左项为参照。全部输出finite，以下是r1，r2逐字节相同。

|输入|参照→实际输出/参照|rRMSE|Cosine|MaxAbs|MeanAbs|差值范围(b−a)|
|---|---|---|---|---|---|---|
|synthetic|A64 → cpu-float|4.78455108e-07|1|3.1303498e-06|8.43900061e-08|[-3.1303498e-06, 3.01736873e-06]|
|synthetic|A64 → gpu-high|5.44439654e-08|1|3.20491381e-07|1.30788678e-08|[-3.20491381e-07, 1.88010745e-07]|
|synthetic|B16_contract → cpu-low|0|1|0|0|[0, 0]|
|synthetic|A64 → B16_contract|0.0126584389|0.999920223|0.0313961562|0.00405029946|[-0.0279029357, 0.0313961562]|
|natural|A64 → cpu-float|6.68811498e-07|1|1.04998762e-05|1.37477605e-07|[-1.04998762e-05, 7.43647979e-06]|
|natural|A64 → gpu-high|6.30897297e-08|1|1.23473001e-06|1.74639902e-08|[-1.23473001e-06, 7.29713065e-07]|
|natural|B16_contract → cpu-low|0|1|0|0|[0, 0]|
|natural|A64 → B16_contract|0.0171932392|0.999853269|0.112455579|0.00624879439|[-0.112455579, 0.105148092]|


**独立B与CPU Memory_Low的16,384+26,624个元素全部逐字节一致，误差为0；没有通过放宽容差取得一致。** A与CPU浮点路径、GPU High仅约5e-8–7e-7相对差异，处于这两条浮点实现与FP64在权重反量化及累加精度/顺序不同的数值边界；本轮不宣称其中哪个浮点实现是绝对黄金，也未逐一分离这些很小的浮点差值。

分解辅助结果：

|输入|比较|rRMSE|MaxAbs|MeanAbs|
|---|---|---|---|---|
|synthetic|A64 → B64_ideal|0.0126743626|0.031783498|0.00405323822|
|synthetic|B64_ideal → B32_prehalf|7.88798654e-08|4.20836841e-07|2.03884451e-08|
|synthetic|B32_prehalf → B16_contract|0.000197804665|0.00138807297|3.73854081e-05|
|natural|A64 → B64_ideal|0.017190464|0.112146542|0.00624905041|
|natural|B64_ideal → B32_prehalf|1.02421523e-07|2.34861363e-06|2.574763e-08|
|natural|B32_prehalf → B16_contract|0.000194441293|0.00304889679|4.4663326e-05|


A→B64_ideal已重现约1.27%／1.72%的差异；B64_ideal→真实FP32后处理约1e-7，随后FP16输出约2e-4。说明本路径的显著差异来自输入动态量化语义，FP32/FP16舍入提供较小附加差异；这些误差对照采用各自参照，不能直接相加为百分比贡献。完整两端数值范围、差值范围、P50/P99元素绝对误差及finite见[errors.csv](analysis/errors.csv)与[results.json](analysis/results.json)，元素分位数不是独立请求的统计置信区间。

## 6. 初版参照不一致的处理

初版主机参照对所有Token套用一般后处理链。synthetic全部一致，natural有6个元素不同，全部集中Token12，最大差6.103515625e-5。没有把它包装成Backend Bug或直接用FP16容差忽略。

核查真实汇编TILE_1发现：该尾部先融合scaleEff，再与running accumulator直接FMA；一般路径是先独立算块结果再加running accumulator。按该源码顺序修正**独立参照程序**后，6处差异全部归零；没有修改Runtime数学代码。初版源程序、可执行文件和原始结果保存在[evidence/reference-attempt1](evidence/reference-attempt1/reference.cpp)，逐元素差值清单在analysis/results.json。复盘教训是先确认实际tail/metadata/精度分支，不用一个抽象量化公式覆盖不同指令级执行顺序；该教训只留在本独立项目，没有改固定上游skill或原阶段证据。

## 7. 功能验证与诊断成本

独立诊断库编译成功、真机10个进程退出0；每进程只执行单Q三次。原图子路径仍使用同一原权重。Tracing ON/OFF与归档CPU输出精确一致，真实入口全3次验证，独立输入整数与scale精确重建，权重及prepared metadata精确核对，B输出精确复现，形成互相可核查的链条。

Tracing宏仅在新构建启用，`MNN_GATEC3_PREFIX`缺省未设置，不写trace。Tracing在计算中只复制buffer到独立内存，完成计算后flush；load阶段权重另行保存。没有改变kernel数学、线程/ISA选择或模型图。每次执行会额外复制/写出约MB级数据，**成本很明显**：

|输入|诊断构建Tracing OFF：r0/r1/r2 ms|同构建Tracing ON：r0/r1/r2 ms|
|---|---|---|
|synthetic|0.658438, 0.538854, 0.525885|1.932188, 1.616562, 1.646927|
|natural|1.081719, 0.905572, 0.868854|5.894271, 2.018177, 2.113906|


这些是宿主`runSessionWithCallBackInfo`墙钟时间，包括相同callback的输入/输出文件写入及Tracing时额外拷贝/落盘，r0还含首次行为；不是Kernel时间或正式性能样本。每条件只有3次，没有随机区组，设备状态/库布局/调度等也会影响数字。因此仅报告诊断成本的实际范围，不能据此推断正常推理性能、精确开销比例或加速收益。归档库、诊断OFF和ON的完整原始值均保存。

日志中WSL localhost代理/systemd警告与上游CMake/编译warning原样保留，实际构建和运行退出码另行判断。没有Root、SELinux修改或NPU操作。

## 8. 停止条件与下一阶段决策

**A：现有证据支持预期量化误差，不建议修改Runtime。当前第一层Q算子正确性定位到此结束。** 不需要为已解释的数值差异编造修复补丁；此处采集补丁仅用于诊断，不能称性能或正确性修复。

结论只覆盖固定两个输入、第一Q、CPU ARMV86 w4 FP16、mode0及固定参数。未证明所有其他配置/算子均正确，也未确认完整模型任务质量。C1/C2原Logits探索性阈值和失败结论全部保留，**本轮A不等于GPU整体精度验收通过**。

下一阶段应独立定义固定语料、teacher forcing/自由生成边界、任务级质量与排序指标，再判断可接受的CPU/GPU行为差异。那是新的模型质量验收范围，本轮不自动执行，不继续全模型逐层排查、无限Profiling或性能优化。

## 9. 交付

[README](README.md)列复现命令与原始证据索引；[protocol.md](protocol.md)为实验协议；[精确计算契约](精确计算契约与源码位置.md)有全部源码位置。独立提取、解码、参照、分析、构建、真机脚本均在scripts，原始文件不依赖报告表格重建。artifact-manifest锁定交付哈希，最终验证区分本路径功能解释与全模型质量通过。
