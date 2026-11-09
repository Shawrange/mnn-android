# 最终技术报告｜Android端侧LLM Runtime研究

## 最终工程判断

固定模型可以在小米15 CPU和Adreno OpenCL上真实执行；构建、基线、调用链、热点、局部量化数值与任务质量都有原始证据和独立分析工具。未发现值得在当前项目中实现的Runtime修复，固定应用质量验收失败。有限CPU/GPU成本比较完成后停止研究，冻结项目；不以必须有加速或补丁作为成功标准。

MNN 3.6.2，commit `7e3c6fb5225d3ccf22807ee641332669df34650d`；Qwen3-0.6B-MNN revision `34dfccda1187ded6e07ea06426da576b0b793c6b`。小米15（Snapdragon 8 Elite / Adreno830 / Android16），Windows + WSL2 Ubuntu + Linux NDK r27c / Clang18 / CMake / Ninja / ADB。桌面RTX4060Ti未承担本项目推理实验。

## 1. 可执行、可审计的Android链路

Linux NDK r27c交叉编译ARM64 Android21，Release/C++17/c++_static/ARM82/LOW_MEMORY/TRANSFORMER_FUSE，Ninja构建。核对AArch64、Android PIE、动态依赖和LOAD alignment0x4000；实际手机4KiB页，不声称另一16KiB设备已验证。CPU459构建步骤、OpenCL各625步骤，实际日志及退出码保存。源码tracked clean；诊断worktree隔离。

模型是固定revision预转换发布资产，图/权重LFS SHA256和其余Git blob OID已核对。完整原始export参数/exporter commit未公开，不能声称能从原始checkpoint逐字节重建同一资产。模型图包括28层Attention、196个4bit投影与1个8bit词表头；“4bit模型”不意味着所有线性层同位宽。

## 2. Benchmark契约决定比较边界

`llm_bench -pg`先Prefill指定IDs，再从同一KV生成；reuse_kv=false使下一请求逻辑历史重置。rep1是完整warmup加一个测量，load/tuning在前。effective dynamic_option对短prompt为0、512prompt为8，Gate1因此保留条件差异，最终三组pp32/128则均0。

Prefill计时不含embedding，Decode计时不含sample但含逐步embedding、tokenizer decode、forward、状态维护；N个输出还执行N次forward。原生gettimeofday并非单调时钟，async=false走原生readMap/wait。Timer不是TTFT或用户E2E；`time -v`涵盖加载到退出且RSS不是GPU显存。成功JSON缺少直接count导出，最终通过独立功能count核验补强，但明确保留正式逐次count没有直接留档的限制。

## 3. 从KV机制到算子热点

Gate1的128+64/128+256 Decode中位91.53/85.58 tok/s只是历史会话。Gate2-A在独立分支增加热路径缓冲观测，退出统一写文件，CLOCK_MONOTONIC记录每步及Attention/KV scope；clean/OFF/ON两输入完整输出IDs一致。长生成内首末64步Attention中位0.95→1.70ms/Token，占比8.71→14.28%；KV扩容有局部尖峰但贡献较小。上下文增长需要访问历史K/V符合Attention实现，不能把所有下降都归因KV或跨进程温度。

Gate2-B复用官方Profiler及小型公共API工具：Convolution代表线性投影而不是卷积视觉任务，每Token112个Q/K/V/O、84个MLP投影、1个词表头。诊断callback时间中投影占78.57%–82.82%，说明主要成本类别；Profile开销、嵌套与scope另行核查，没有把诊断占比当clean精确占比，也没有把剩余时间都称Runtime调度。缺乏可验证冗余、PMU/带宽上限证据，不做Kernel优化。

## 4. OpenCL是真实执行而非配置名

普通ADB可访问vendor OpenCL，读取Adreno830/OpenCL3.0/驱动0800.71；独立算术Kernel正确。LLM主要线性层和Attention有设备CL事件，Creator诊断无回退日志；Host Tokenizer、采样、shape管理仍在CPU，不能声称100%GPU。clean与profile库分开，Profile会改变等待/提交行为，不能混作正式性能。

GPU `-t 4`的含义是模式位，请求经过OR64/512成580，Buffer/Wide tuning/RecordBatch；实际录制受driver与Backend判断。Android shell可用也不证明APK namespace/manifest集成已完成。Hexagon直接编程与QNN SDK路径仅静态调查，未下载DSP自定义算子或运行NPU。

## 5. 数值差异为何不等于实现Bug

C1/C2探索性Logits门槛失败永久保留。C2核查公共接口、形状/Host布局、同步、重复性及首执行输入生命周期，将显著差异定位至第一层Q/K/V而非相同入口Norm；同Q输入浮点路径与GPU High接近，CPU Low仍有约1%–2%差异。没有将完整Prefill重放假称为与增量Decode算术路径相同的Teacher Forcing。

C3只研究第一Q：实际ARMV86 w4 FP16执行器，输入每Token1024通道一组，权重每64通道一块。独立重建FP16 absmax、FP32 Q/D与FP16乘法、FCVTAS/SQXTN、INT4 nibble/offset解码、INT32分块点积、FP32 FMA与FP16输出。特别追踪TILE_1尾部FMA顺序；初版独立参照6个尾部不一致经按真实顺序修正后归零，Runtime没有修改。

两种输入共43,008输出元素与CPU Low逐字节一致；独立浮点参照与CPU浮点/GPU High仅约5e−8–7e−7相对差异。43,008是元素数，不是独立请求数；FP64参照仍使用同一量化权重，不是原未量化模型golden。结论限于该路径/两个输入/固定metadata mode，支持预期量化语义，不支持全模型万能正确性证明。

## 6. 应用质量决定是否具备使用价值

独立Pilot后冻结100例、每类25：分类、严格JSON抽取、简单指令、确定短问答。CPU/GPU同一Tokenizer/模板、关闭Thinking、greedy、96上限、自然EOS、每例新进程KV0。200/200正常结束，完整输入/输出IDs与原文保留，确定性评分及10项测试通过。

CPU24/100、GPU25/100，配对共同对23、CPU单对1、GPU单对2、共同错74；分类9/9、抽取0/0、指令6/7、问答9/9。抽取代码围栏违反预先直接JSON契约，不能事后剥除再改主分；也有实际内容错误。三条discordance重复结果一致。差值+1pp不代表GPU优越或等价，只有3对成败分歧、样本人工且相关；结论是固定实验组不满足应用要求，非所有Qwen3模型不行。

代表性Logits比较固定Token历史，新进程全Prefill；保留1个重放与原Decode下一Token不同的记录。不把自由生成分叉后的不同历史Logits混比。C3算子解释成立不等于C4模型质量通过。

## 7. 最终有限硬件成本比较

128+64：CPU Prefill/Decode 346.63/93.35 tok/s，GPU 1015.44/71.03 tok/s。以下全部来自本轮36新进程，不与Gate1拼接：

|输入+生成|后端|n|Prefill TPS 中位数 [min,max]|Decode TPS 中位数 [min,max]|Prefill/Decode CV%|Max RSS MiB 中位数|
|---|---|---:|---|---|---|---:|
|32+64|cpu|6|368.15 [343.24,574.19]|96.38 [95.36,97.98]|21.80/0.98|902.3|
|32+64|opencl|6|472.06 [469.50,473.18]|69.97 [68.02,72.50]|0.29/2.90|347.5|
|128+64|cpu|6|346.63 [340.15,528.46]|93.35 [90.82,94.57]|19.50/1.36|902.7|
|128+64|opencl|6|1015.44 [1011.75,1020.57]|71.03 [67.30,71.76]|0.37/2.34|347.0|
|128+256|cpu|6|339.97 [334.50,541.04]|89.73 [89.16,91.15]|22.13/0.91|902.5|
|128+256|opencl|6|1014.73 [1010.95,1021.13]|67.50 [67.30,68.37]|0.34/0.67|347.4|

|负载|配对n|Prefill CPU/GPU 中位[范围]|Decode CPU/GPU 中位[范围]|两Timer之和 CPU/GPU 中位[范围]|
|---|---:|---|---|---|
|32+64|6|1.282 [0.824,1.374]|0.728 [0.704,0.757]|0.754 [0.742,0.795]|
|128+64|6|2.920 [1.923,2.999]|0.764 [0.719,0.790]|1.023 [0.906,1.032]|
|128+256|6|2.986 [1.877,3.032]|0.752 [0.741,0.764]|0.824 [0.787,0.836]|

分阶段GPU Prefill与CPU Decode各有优势。比值>1表示GPU该scope成本较低；两Timer之和排除其他工作，不能称用户端到端加速。n6只给中位/范围/SD/CV，不作尾部稳定性声明；有状态混杂，普通ADB读取GPU频率/忙碌度权限被拒，未改安全机制。

skin快照32.2–34.8°C、电池30.8–32.2°C，CPU频率前后变化保留。首次GPU cache创建与后续warmup分开，未可靠拆出编译耗时。正式输出计数没有直接导出，此限制和功能check依据透明记录。RSS不等于显存。固定生成内容可能不同、质量未过，不能称产品任务加速。

## 8. 工程结案与复核

旧Gate证据不修改。最终核验保护17,089个旧文件，36次正式样本、冻结时间/hash、clean库、原生JSON和统计相互一致；机器可读结果见Gate2-D verification-summary与根project-manifest/PROJECT_FREEZE。离线复核命令见README，构建与真机重现需在新副本使用独立session，不覆盖归档。

本项目交付了部署工具、可追溯实验、可证伪假设和数值参照；没有Runtime加速补丁、上游PR或产品部署。最终停止，不自动开展GPU性能深化、NPU、全模型逐层排查或第二项目。未来如有新需求，应另建范围和资产组，由新任务授权，而非继续扩展本次证据。

## 原阶段附录

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
