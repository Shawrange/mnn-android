# Gate 2-D｜MNN Android CPU/GPU最终性能对照报告

**完成36/36次预定正式运行，全部退出0，无失败替补、无追加性能实验。结果同时支持A和B：OpenCL在这三组负载的原生Prefill scope成本较低，CPU在Decode scope成本较低。项目到此冻结，不进入源码优化或新的GPU/NPU研究。**

这只比较固定输入/生成Token数量下的硬件执行成本。Gate2-C4已判定当前固定模型/关闭Thinking应用配置不达标，该结论继续有效；本轮不是质量等价任务的性能收益，更不是产品级性能验收。128+64：CPU Prefill/Decode 346.63/93.35 tok/s，GPU 1015.44/71.03 tok/s。单scope、配对和设备状态边界如下。

## 1. 固定实验组与正式前冻结

- MNN3.6.2 commit `7e3c6fb5225d3ccf22807ee641332669df34650d`，模型revision `34dfccda1187ded6e07ea06426da576b0b793c6b`，小米15/SM8750/Adreno830/Android16。
- CPU使用Gate0归档clean库，GPU使用Gate2-C clean库，CLI两端相同。没有重编译Runtime，没有Tracing/Profile宏、`--profile`、debug callback或额外同步。
- CPU4线程；GPU `-t 4`经源码成为模式580=Wide tuning4|Buffer64|RecordBatch512请求，不是GPU线程数。录制队列实际启用仍依赖驱动能力；本轮没有为正式样本插入事件采集。
- 两端Low precision、Low memory、Normal power、greedy、ignore_eos、async=false、reuse_kv=false、mmap=false；requested dyo0，三负载effective dyo均0；qa0/fa1→attention_mode8。相同权重、Tokenizer、llm_config。原始Token输入为32或128个ID16，无聊天模板/Thinking提示的真实问答语义。
- 协议冻结UTC `2026-11-09T08:33:47.551684+00:00`，正式开始 `2026-11-09T08:33:47.727121+00:00`，结束 `2026-11-09T08:46:32.722657+00:00`；所有哈希在[freeze.json](freeze.json)。6区组，每区组打乱3负载，同负载两后端相邻并随机顺序，seed20261109；18对、36独立进程。
- [源码与指标边界](源码与指标边界.md)给出真实函数/行号；[protocol.md](protocol.md)保留正式前声明。

## 2. Pilot、加载、Kernel缓存与warmup

最初Pilot共3进程完成推理，但CLI `-m config.json`使模型大小元数据错误（路径无斜杠，文件大小返回异常值）。全部原始记录保留，独立[pilot-review.json](evidence/path-compatibility/pilot-review.json)明确判定不能用于比较；原记录中的success只代表当时runner未识别此元数据问题，不作为最终有效Pilot。一次范围明确的源码核查定位`getDirectoryOf`，改为`./config.json`，在新部署目录symlink至原权重，未修改源码/模型。修正后3/3 Pilot元数据与执行均成功；这些均不混入36次。

新GPU工作目录起初没有MNN cache；首次原始stdout保留`Can't open file:tmp/mnn_cachefile.bin`和`Update cache ... size=707228`，结束后cache文件归档。首次32+64整进程wall为4.873s，修正路径后的同负载Pilot为3.346s。首次记录模型大小无效且两次状态/页缓存也不同，**差值不能认定为纯Kernel编译耗时**。没有单独导出load/compile/tuning各自时间，缺失即缺失；只保留初次准备生命周期及cache变化。首次没有MNN磁盘cache也不代表驱动所有缓存冷。

`-load false`只load一次，CPU `tuning_prepare`在计时前，OpenCL `Llm::tuning`直接返回。`-rep 1`在同一进程执行1次完整同负载warmup，再1次测量；warmup不入JSON。正式跨进程复用本轮缓存，保持同一机制，不清页缓存/系统缓存，不称严格冷启动或完美锁频稳态。一次warmup不能证明彻底排除全部编译/准备效应。

## 3. 请求配置、实际长度和模型状态核查

先使用独立公共API count_probe，链接相同clean库、相同配置与输入，仿照官方调优与OpenCL switchMode，每后端3负载×2连续response。12次功能请求均直接核对 `gen_seq_len == output_ids.size() == requested`、最终KV=pp+tg，状态MAX_TOKENS_FINISHED；首次及后续请求均符合。完整有效配置、输入/输出IDs保留在 `results\functional-20261109T083146Z`。CPU/GPU六对功能输出IDs均不同，不能视作相同答案质量。

正式CLI原生JSON的generate_len为**请求值**，实际count仅用于其内部TPS分子，成功时不导出output IDs/gen_seq_len。36次均无Incomplete sample/执行错误，配置与固定ignore_eos生成循环相符，count_probe提供独立直接佐证；**仍没有每个正式进程直接导出的实际count，不能假称逐次读取验证了它**。此工具界限永久保留。若要求每次成功count直接留档，需要另行扩展CLI输出；本项目按用户固定干净CLI的边界结束，没有为此改Runtime或补跑样本。

每次原生JSON均CPU/OPENCL、t字段4、precision2、memory2、power0、qa0/fa1、mmapfalse、唯一正确pp/tg，模型权重大小429.93MiB。模型初始化错误、无效JSON、非零退出、回退/错误标记均导致失败并停止。最终36/36成功，0失败，六cell各6；原始JSON未改写。正式过程中未直接读取Llm dump_config，由冻结配置/CLI映射源码/功能dump共同核查有效选项，不把请求字段当作设备实测计数。

## 4. 主要结果

单位tok/s。范围为6个独立进程min/max，CV为n−1样本标准差/均值。更多mean、SD、MAD见[summary.json](analysis/summary.json)，没有P95稳定性或SLA声明。

|输入+生成|后端|n|Prefill TPS 中位数 [min,max]|Decode TPS 中位数 [min,max]|Prefill/Decode CV%|Max RSS MiB 中位数|
|---|---|---:|---|---|---|---:|
|32+64|cpu|6|368.15 [343.24,574.19]|96.38 [95.36,97.98]|21.80/0.98|902.3|
|32+64|opencl|6|472.06 [469.50,473.18]|69.97 [68.02,72.50]|0.29/2.90|347.5|
|128+64|cpu|6|346.63 [340.15,528.46]|93.35 [90.82,94.57]|19.50/1.36|902.7|
|128+64|opencl|6|1015.44 [1011.75,1020.57]|71.03 [67.30,71.76]|0.37/2.34|347.0|
|128+256|cpu|6|339.97 [334.50,541.04]|89.73 [89.16,91.15]|22.13/0.91|902.5|
|128+256|opencl|6|1014.73 [1010.95,1021.13]|67.50 [67.30,68.37]|0.34/0.67|347.4|

CPU Prefill的CV为19.50%–22.13%，明显大于GPU的0.29%–0.37%。CPU出现三次较高TPS：32+64区组3为574.19、128+64区组6为528.46、128+256区组2为541.04，均保留，不按速度剔除；同组其他CPU样本多为约334–371 tok/s。有效dynamic_option相同，现有频率/温度快照不足以解释这些进程差异，不能包装成Runtime模式变化、Bug或因果归因。

RSS是进程Max RSS；不能把OpenCL RSS较低解读为总GPU内存占用较低，驱动共享/映射分配记账不同，未测GPU显存/PSS。

派生阶段毫秒是单样本Token数/TPS×1000，再在6个进程上取中位数；未把中位TPS的倒数冒充中位阶段时间。原生rep1的std0表示单个有效观察，绝不表示设备稳定。

|负载|后端|Prefill ms中位|Decode ms中位|整进程wall秒中位[范围]|
|---|---|---:|---:|---|
|32+64|cpu|86.921|664.017|2.578 [2.530,2.607]|
|32+64|opencl|67.787|914.965|3.278 [3.090,3.373]|
|128+64|cpu|369.272|685.562|3.164 [2.915,3.228]|
|128+64|opencl|126.054|900.997|3.406 [3.249,3.498]|
|128+256|cpu|376.502|2853.061|7.499 [7.138,7.570]|
|128+256|opencl|126.142|3792.430|9.226 [8.859,9.266]|

整进程wall包括load、tuning、warmup、测量、退出；**不是单请求端到端**。本轮没有可靠单请求E2E和完整TTFT记录，两者为null，没有用这些表推导用户延迟。

## 5. 同区组配对执行时间比

比值=CPU阶段时间/GPU阶段时间；>1意味着该scope GPU成本较低，<1意味着CPU成本较低。两Timer之和只组合被观测scope，排除采样、输入embedding等范围，不能称完整推理时延。配对是相邻新进程，未混入Gate1历史CPU。

|负载|配对n|Prefill CPU/GPU 中位[范围]|Decode CPU/GPU 中位[范围]|两Timer之和 CPU/GPU 中位[范围]|
|---|---:|---|---|---|
|32+64|6|1.282 [0.824,1.374]|0.728 [0.704,0.757]|0.754 [0.742,0.795]|
|128+64|6|2.920 [1.923,2.999]|0.764 [0.719,0.790]|1.023 [0.906,1.032]|
|128+256|6|2.986 [1.877,3.032]|0.752 [0.741,0.764]|0.824 [0.787,0.836]|

- 32+64：Prefill GPU成本较低 5/6对；Decode CPU成本较低 6/6对；两Timer之和GPU成本较低 0/6对。
- 128+64：Prefill GPU成本较低 6/6对；Decode CPU成本较低 6/6对；两Timer之和GPU成本较低 4/6对。
- 128+256：Prefill GPU成本较低 6/6对；Decode CPU成本较低 6/6对；两Timer之和GPU成本较低 0/6对。

分阶段优势方向比“GPU整体更快”更准确。原生阶段比较支持局部执行成本判断；对于接近1或跨1的合计结果，应保留设备状态与样本波动边界，不从n6外推普遍排序。完整每区组值见[paired-ratios.csv](analysis/paired-ratios.csv)。不增加样本去追求更有利的结论。

具体而言，32+64和128+256的两Timer之和CPU均为6/6对成本较低；128+64比值中位1.023、范围0.906–1.032，排序跨1，不作稳定整体胜负判断。这些是scope相加的有限成本结果，不是完整端到端延迟。

## 6. 设备、内存与调度状态

每次前后共72个原始状态快照，USB供电均为True，电量范围[100.0, 100.0]%，屏幕状态['Dozing']，thermal_status为[0.0]。skin 32.2–34.8°C，battery 30.8–32.2°C，当前HAL CPU最大温度35.3–64.9°C；GPU HAL最大传感器快照34.3–59.0°C。实际冷却15.45s中位，范围15.33–15.67s，额外轮询0次运行。没有改系统电源、亲和性、时钟或安全设置。

|policy|cur_freq快照范围kHz|scaling_max_freq快照范围kHz|
|---|---|---|
|policy0|748800–2745600|2745600–2745600|
|policy6|1017600–2841600|2649600–2841600|

这是开始/结束时的CPU频率快照，不能代表整个模型执行区间，不用于声称锁频或建立温度/频率因果。进程context switches/faults均包含加载、预热和测量，原始time -v及[device-state-summary.json](analysis/device-state-summary.json)保留，不把OpenCL进程的切换次数直接解释为Decode调度开销。

普通ADB读取GPU gpuclk/cur_freq/gpubusy在36次before及after返回Permission denied，原始stderr保留；没有绕过权限。没有执行期间GPU频率/利用率/能耗，也没有把全局MemAvailable当进程内存。当前结果只适用于原生调频/调度及这些温度门槛的本次会话。

## 7. 执行路径、产物与可追溯性

clean库与Gate0/C0-C1逐字节相同，CPU SHA256 `47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e`；GPU `4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61`；官方CLI `fd85bf65a75656d023feb9e2ad315f6ee7c6033c8f1591a835e54d2985db4676`。权重SHA256 `953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`。

新部署 `/data/local/tmp/mnn-gate2d-20261109T082806Z-5d76d2`；模型只读复用旧目录。设备端/本机模型、配置、库和CLI hash核对，原始ELF/NEEDED及Release CMakeCache/Ninja实际编译命令在evidence。正式构建无GPU_TIME_PROFILE、DUMP_PROFILE_INFO、Gate诊断宏，未调用--profile。OpenCL使用系统vendor驱动，不替换libOpenCL。

实际GPU证据复用C0/C1和C4同一模型、同一后端模式的设备事件：主要线性Convolution与28层Prefill/Decode Attention均有CL START/END事件，诊断无Creator回退日志。此次clean Benchmark新cache和无执行错误提供补充佐证。**没有对正式36次逐算子采事件，不宣称整个进程100%GPU，也不声称排除了每个算子的所有CPU回退**。Tokenizer、采样等Host工作本就位于CPU；不能仅凭配置字符串或文本输出宣布GPU执行。

## 8. 限制、工程决策与停止

1. 三个人工Token负载、单手机/单驱动、每cell n6，不代表真实聊天/长上下文总体；Greedy输出可不同。当前固定应用质量契约失败，任何阶段优势都不能包装成可用产品的加速。
2. 正式输出计数只能由源码约束与独立功能核验支持，未逐次直接导出；原生Timer使用gettimeofday，scope不含完整请求；启动/编译细分、TTFT、请求E2E、PSS、GPU显存、能耗缺失。
3. 未锁频，温度与CPU策略有状态变化；GPU频率权限不足。区组交错减少部分时间漂移，不能消除所有干扰，也不能将跨进程相关性称为因果。
4. 原有C1/C2探索性Logits阈值失败、C3预期量化解释与C4质量失败全部原样保留；这轮成本比较不改变这些结论。

**最终A+B：GPU Prefill、CPU Decode各有执行成本优势；不作“GPU全面加速”或用户体验收益声明。** 完成预定36次后停止所有推理；没有追加Kernel Profiling、源码优化、模型替换或NPU实验。整理根README、FINAL_TECHNICAL_REPORT、INTERVIEW_GUIDE、RESUME_PROJECT，按根PROJECT_FREEZE.json正式冻结。项目成功之处是可复核的工程解释与清晰停止条件，不是强行得到优化补丁。

交付：[samples.csv](analysis/samples.csv)、[原始会话](results/formal-20261109T083347Z-e5bcfa)、[统计程序](scripts/analyze.py)、[状态统计](scripts/summarize_state.py)、[独立核验](scripts/verify.py)、[verification-summary.json](verification-summary.json)。此前17,089原文件逐个hash复核，不修改原始证据。
