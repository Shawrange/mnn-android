# Gate2-C2｜CPU/GPU数值差异定位报告

**结论C：差异已定位到第一层量化线性投影的不同计算路径，值得进行针对性的数值语义验证；目前没有证据要求修改Backend。** 原有Prefill Logits比较未发现Token位置、模型状态、Host dtype或同步错配。两个Low输入的第一层Norm与Q投影入口逐字节相同，Q/K/V出口已分歧。固定同一Q输入后，同一原权重的CPU High/Memory_High浮点反量化路径与GPU High相对误差仅约4.8e-7／6.7e-7，而CPU Memory_Low与该参照约1.27%／1.72%。这强烈支持CPU动态输入量化执行路径是**最早显著分歧**的重要来源，不能把最终Logits全部误差归于它，也不能据此认定CPU或GPU有Bug。

## 1. 固定资产与边界

MNN3.6.2 commit `7e3c6fb5225d3ccf22807ee641332669df34650d`；模型revision `34dfccda1187ded6e07ea06426da576b0b793c6b`，权重SHA256 `953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`。小米15/SM8750/Android16，ADB普通shell，无Root或安全配置变化。Windows/WSL Ubuntu/NDK r27c。

CPU运行Gate0归档libMNN，SHA256 `47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e`；实际完整CPU/GPU库哈希见每会话verified-assets或executable-evidence及[evidence/environment/device-artifacts.json](evidence/environment/device-artifacts.json)。GPU运行Gate2-C clean库，SHA256 `4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61`。模型图和权重未修改、未重导出、未重新量化。所有主对照memory=low、power=normal、dynamic_option=0、attention_mode=8、mmap/async/reuse_kv=false；CPU4线程，GPU请求4自动编码580，**不是GPU4线程**。

唯一额外改变memory的实验是独立单算子辅助参照CPU High/Memory_High，不替换CPU基线，也不用于性能结论。没有Runtime/Kernel源码修改，没有诊断分支补丁；工具只调用现有接口，并只读Tensor backend元数据。没有GPU性能矩阵、优化或NPU实验。开始时保护前期6318个文件，最终核验见[verification-summary.json](verification-summary.json)。

## 2. 原有方法复核

详细函数与固定行号见[源码与方法核查](源码与方法核查.md)，38份源码快照均与git show固定提交逐字节核对。

`response(ids,nullptr,nullptr,0)`：generate_init在reuse_kv=false时清历史及逻辑长度，generate先Prefill、更新状态，只有max_tokens>0才采样/Decode。forwardRaw默认all_logits=false，选择logitsLastIdx=-1；getOutputs返回本次mGenerateParam.outputs。因此输出是**完整输入最后位置用于预测下一Token的原始Logits**，不是首位置，也不是执行一次Decode后的Logits。两输入分别8个token16及固定中文模板13Token；输入IDs逐项核对，形状[1,1,151936]，prompt/all_seq_len/kv_history均与输入长度相同，generated=0；这是本轮实际状态检查，不仅依赖配置。

readMap<T>模板是指针类型转换，本身不保证或转换dtype。工具先检查getInfo nominal float32，再读取；GPU内部Low存储可为FP16，不能由Host f32倒推设备精度。Variable::readInternal会按后端复制到Host；OpenCL copyFromDevice进行精度/布局转换后CL_TRUE读取；forwardRaw在async=false下还wait。每个输出连续两次readMap均逐字节一致；全部Logits finite。连续读取可能共享Host缓存，不能单独证明两次设备执行；完整重新Prefill的重复性另行检查。

检查点使用Llm::setDebugCallback/enable_debug，活跃张量生命周期内wait并copyToHostTensor到独立CAFFE/NCHW float32缓冲。保存原shape、format、nominal type、Backend及Host shape、copy/wait结果，之后才落盘。这样去除NC4/NC8打包填充，不把packed内存直接解释为float32，也不延迟持有可被arena复用的Tensor指针。shape相同仍需检查op_name/phase，分析脚本同时校验。

**复核结论：没有发现需推翻C1比较的系统性方法错误。** C1原有两个失败结论不改。新建隔离工具则发现并修正了自身的输入复用问题，见第7节；这与原LLM接口的比较分开处理。

## 3. 样本、重复性与诊断扰动

完整LLM工具22个有效进程：pilot2、Low无debug8（每后端/输入2进程）、High无debug4、正式少量检查点8。每进程一次Prefill预热，随后两次完整重新Prefill，保存44份完整Logits。仅**2种独立输入**；重复进程与151936词表元素不充当独立请求样本，也不据此宣称广泛确定性/质量。

|对照|张量配对数（不是请求数）|逐字节相同|最大MaxAbs|
|---|---|---|---|
|within_process|132|132|0|
|cross_process|4|4|0|
|debug_vs_off|10|6|0.21875|
|C1_vs_C2|4|2|0.21875|


within_process包含Logits与已选检查点，共132对全部相同；Low无debug跨进程4对Logits全部相同。High只做进程内重复，未扩展High跨进程矩阵。单次输出两次Host读取也全部一致。各后端在已覆盖条件下可重复，不等于所有driver/tuning/cache状态都逐位一致。

OpenCL debug对比无debug：Low synthetic rRMSE约0.00145（另一pilot约0.00153），natural约0.00719，Top1相同；High synthetic约1.5e-7，natural逐字节相同。CPU debug/off全部逐字节相同。新的GPU Low与C1也有小幅差异，CPU与C1逐字节相同。不同新进程、cache/tuning及同步路径同时存在变化，**不能把全部差异因果归于callback**；也不能宣称callback完全无数值扰动。层级数据用于定位诊断路径，后续固定Q子路径复现两端Low完整模型的Q输出逐字节一致，加强了这处局部观察的可信度。

## 4. Precision实际语义与Logits结果

CPU initRuntime把high/low映射Precision_High/Low；手机支持fp16arith，CPUBackend::onCreate在Low选择Arm82Backend。检查点实际backend=13且第一层Norm/Q全部值可精确表示为half；High backend=0，half格点占比仅约0.02%–0.10%。这与源码选择和数值表现一致，证实切换生效。

OpenCL在驱动支持FP16时保留请求precision；High使存储及通用COMPUTE_FLOAT宏为float，Low为half（具体kernel仍可显式float归约，不能说每条指令都是half）。两模式检查点backend=3，Low第一层Norm/Q全部在half格点，High仅约0%–0.10%。固定权重量化位宽不随precision改变。尤其**CPU High+Memory_Low仍走动态输入量化执行器族，不是取消激活量化的FP32 oracle**。

下面为无debug、预热后的第一份完整Logits；未平均跨条件数据：

|模式|输入|rRMSE|Cosine|MaxAbs|MeanAbs|界内比例|Top1|Top5交集|CPU/GPU margin|初筛|
|---|---|---|---|---|---|---|---|---|---|---|
|low|synthetic|0.066681008|0.99781587|1.3883057|0.20567668|47.36%|True|4|1/0.875|未通过|
|low|natural|0.11364733|0.99396174|3.3554688|0.56306316|25.21%|True|4|7.453125/7.703125|未通过|
|high|synthetic|0.064853935|0.99791896|1.3591254|0.20221827|48.05%|True|5|1.1320095/0.91108799|未通过|
|high|natural|0.12099313|0.99410362|4.150835|0.59331454|21.50%|True|3|8.2607746/7.7628231|未通过|


指标以CPU为参照a、GPU为b：rRMSE=sqrt(sum((b-a)^2)/sum(a^2))，cosine=dot(a,b)/(norm(a)*norm(b))；同时记录max/mean abs、两端范围和finite。C1探索性阈值保持rRMSE≤0.02、cosine≥0.999、满足abs(b-a)≤0.1+0.02*abs(a)的元素比例≥99.9%，并要求IDs/shape一致和全部finite。它们不是官方规范或任务质量标准。四组均未通过，未追溯调整阈值；C1原始两例失败保持不变。

High synthetic略小、natural反而较大，不能以High命名假定更接近CPU/GPU，也不能仅凭误差变化确定根因。完整Top5、两端margin、排序变化标记在[metrics.json](analysis/metrics.json)；这四对Top1均相同，Top5仍有顺序/成员变化。并非词表151936个独立样本。

## 5. 少量层级检查点

先选11处：第一层Norm入口/出口、Q入口及Q/K/V出口、第一Attention出口、第一块末残差、最终Hidden State、最终Norm及词表头。两输入/两precision都保存，未dump全图。Q输入canonical shape为[8或13,1024,1,1]，Q输出[8或13,2048,1,1]；hidden_states为[1,8或13,1024]，最终Norm为[1,1,1024]，词表头为[1,151936,1,1]。完整shape/dtype/layout/backend见每run meta。

|检查点（Low，完整Prefill）|synthetic rRMSE / MaxAbs|natural rRMSE / MaxAbs|
|---|---|---|
|embedding_on_backend|0 / 0|0 / 0|
|_input_layernorm_Mul_1_output_0|0 / 0|0 / 0|
|q_input|0 / 0|0 / 0|
|_layers_0_self_attn_q_proj_Linear|0.012686314 / 0.03125|0.017227263 / 0.11132812|
|_layers_0_self_attn_k_proj_Linear|0.011517017 / 0.0390625|0.015182337 / 0.11523438|
|_layers_0_self_attn_v_proj_Linear|0.031143258 / 0.015296936|0.052443468 / 0.0597229|
|Attention_Reshape_8_output_0|0.031154103 / 0.015304565|0.059427019 / 0.079589844|
|_Add_4_output_0|0.054897481 / 0.08203125|0.078436357 / 0.3190918|
|hidden_states|0.10645759 / 350|0.08934334 / 236|
|_norm_Mul_1_output_0|0.089829142 / 4.125|0.15702042 / 3.484375|
|_lm_lm_head_Linear|0.066812542 / 1.3922119|0.1143555 / 3.3867188|


Low两输入在Norm及Q入口完全相同，第一可见显著误差是量化投影。High synthetic同样入口完全相同；High natural在第一Norm/Q入口已有约4.26e-8相对误差、最大2.38e-7，因此**若按任何非零差异定义，High natural最早微小分歧在Norm**；投影出口随后达到约1.72%，不能把tiny Norm差异忽略后声称完全相同。

Q/K/V、Attention与残差在后续层传播/累积；最终Hidden State的绝对范围较大，MaxAbs单独不能衡量异常。所有44个跨后端检查点对的rRMSE、cosine、max/mean abs、两端min/max、finite见[checkpoint-errors.csv](analysis/checkpoint-errors.csv)。没有把上游误差传播当成Attention或词表头各自的独立实现错误。

## 6. 原图第一层Q投影的同输入隔离

通过Interpreter ScheduleConfig::Path::Tensor选择原始q_proj输入和输出，saveTensors保留中间结果；原文件和external weight直接加载。只有一个数学Convolution，允许Runtime插入Raster布局转换；不含Attention、KV或采样。两端用CPU Low保存的完全相同q_input，两种precision都使用该共同输入（因此High隔离与High整图入口有小幅差异）。最终主会话 `results\replay-20261108T203707Z-62dfec`，10进程，每个r0首次执行，r1/r2为入口回读已验证的有效配对；两次输出逐字节相同。

|相同Q输入的比较（第一项为参照）|输入|rRMSE|Cosine|MaxAbs|MeanAbs|
|---|---|---|---|---|---|
|cpu-low-low → opencl-low-low|synthetic|0.012686314|0.99991993|0.03125|0.0040636053|
|cpu-high-low → opencl-high-low|synthetic|0.012650717|0.9999202|0.031376362|0.0040498744|
|cpu-high-high → cpu-high-low|synthetic|0.012660215|0.9999202|0.031378269|0.0040498779|
|cpu-high-high → cpu-low-low|synthetic|0.012658459|0.99992022|0.031396031|0.0040503051|
|cpu-high-high → opencl-high-low|synthetic|4.7974319e-07|1|3.3378601e-06|8.5686111e-08|
|cpu-high-high → opencl-low-low|synthetic|0.00080374359|0.9999997|0.0024940968|0.00024487025|
|cpu-low-low → opencl-low-low|natural|0.017227263|0.99985264|0.11132812|0.0062590753|
|cpu-high-low → opencl-high-low|natural|0.01715111|0.99985354|0.10951662|0.0062341493|
|cpu-high-high → cpu-high-low|natural|0.017172855|0.99985354|0.10951066|0.0062341439|
|cpu-high-high → cpu-low-low|natural|0.017193224|0.99985327|0.11244988|0.0062487914|
|cpu-high-high → opencl-high-low|natural|6.6926885e-07|1|1.0490417e-05|1.387798e-07|
|cpu-high-high → opencl-low-low|natural|0.00088664657|0.99999964|0.016459465|0.00029870502|


Low隔离Q与完整模型callback的Q输出两端、两输入均逐字节相同，说明局部路径复现成功。CPU High/Memory_High改为同一权重的浮点反量化/浮点矩阵计算参照；它不是原始未量化模型、FP64实现或官方golden。GPU High与该参照接近到1e-6量级，而CPU Low/High+Memory_Low仍约1%–2%；GPU Low对参照约8e-4–9e-4。**支持的最窄结论是：第一Q投影差异主要随CPU动态量化计算路径而变化，单纯FP16不足以解释该处差异。** memory同时改变执行器/权重展开/打包/累加，尚未单独捕获量化输入和scale复算，因此不把动态量化舍入认定为唯一机制，也不推导最终Logits的误差份额。

CPU源码：ConvolutionFloatFactory::create/_createUnit在Memory_Low选择动态量化DenseConvInt8执行器族（可经extension），构造参数true设置mDynamicQuant；执行时BatchSym/AsyDynamicQuant将浮点输入转为整数再GEMM。Memory_High通过ConvolutionCommon::load展开同一量化权重、DenseConvolutionTiledExecutor走浮点MatMul。当前未精确追踪最后的ISA函数指针，不能随意命名具体i8mm/sdot kernel。

GPU源码：ConvBufLowMemoryExecution在batch8/13进入tuneGemmLowMemory的global_y<=16分支，包含c4nhw4→nhwc布局kernel、gemv_conv_c8_buf(COMPUTE_BATCH)及返回布局；不是大batch的gemm_b4/b8路径。gemv kernel解包权重、使用scale/offset反量化，再与浮点输入作乘加/归约，没有CPU式输入INT8动态量化。源码路径与实际backend3、shape、局部输出一致；本轮未逐个记录内核build options或最终WGS，故不越界声明已采集所有kernel参数。

## 7. 失败、排除与未解决的观测边界

隔离工具初次编译错误是将Interpreter方法误写setHint；已改为固定版setSessionHint，原编译错误/退出码保存。第一次运行exit11因未saveTensors找不到中间输出；第二次exit13是校验错误地不允许Runtime Raster，均不是模型不支持。随后早期完整会话缺逐次入口核验，下一版暴露CPU输入arena复用：只上传一次后，r1/r2已不是原输入。最终工具每次执行重新上传，入口回读作为硬门禁；原文件不改。

原始隔离会话共32个进程尝试，其中2个退出失败、20个较早版本即使退出0也明确排除，最终10个作为主配对。失败与排除清单在[replay.json](analysis/replay.json)。analysis主工具不会把退出0等同有效同输入实验。

最终GPU r0的before回调入口读数仍与源不同，但r1/r2正确，三次最终输出相同。Pipeline的before在execution前执行；初始化/输入物化时点仍可能影响首次读数，**本轮没有确定其完整机制**，不把该读数冒充kernel消费值、不计入同输入归因。只用源数据与实际入口逐字节相同的r1/r2进行隔离结论；r0原始数据和错误差值保留。后续如研究首次回调语义，应单独设计After-copy检查，不修改系统安全或Kernel数学。

WSL偶发localhost代理/systemd用户会话警告保留；本轮编译与源码读取实际成功，未据警告假定环境失败。所有手机推理均有stdout/stderr/退出码和前后设备状态；未测性能，不以温度或频率变化解释数值误差。

## 8. 决策、假设和可证伪的下一步

**选择C，范围限定为已定位的不同计算路径；目前不建议Runtime补丁。** 不是A：C1比较未发现系统性错位；也不是B：High没有消除差异，CPU动态输入量化仍在。最终Logits误差贡献尚未全量解释，有D的保留边界，但并非毫无线索。

1. **优先验证动态输入量化的预期误差。** 观察：同Q输入下CPU浮点参照与GPU High接近，CPU Memory_Low偏差明显。下一步只对第一Q/K/V捕获动态量化后的整数输入、scale/zero和同一反量化权重，用独立高精度矩阵计算复算；若能解释CPU出口，支持预期量化误差；若偏差超出复算则继续查scale、布局和GEMM。当前没有独立FP64 golden，不判断哪条路径绝对正确。
2. **精度传播与任务质量门禁。** 观察：早期小误差到最终隐藏状态/Logits增大，Top1在两输入仍相同。下一步固定更多短输入和teacher-forcing前缀，先选早层/中层/最终层少量检查点，建立基于任务的容差和排序/质量验收；保留本次探索阈值，不能用改阈值覆盖失败。此项是质量标准研究，不是性能调参。
3. **诊断路径与首次读数。** 观察：GPU debug/off小幅不同，首次隔离before输入读数不能直接使用。下一步固定cache/tuning条件，比较只登记callback、仅等待、选点复制三种诊断及首/后次执行；在不改数学结果前提下核查copy与callback时序。解释仍待验证，不能归为GPU竞态Bug。

若第一项证实误差来自预期量化策略，应停止寻找虚构Bug，转入独立质量验收。当前不建立正式GPU性能基线，不宣称加速，不启动NPU。后续工作需另行限定范围，本轮到此结束。

## 9. 交付与复现

[README](README.md)包含复现命令、原始会话与数据索引；[protocol.md](protocol.md)保留预先判据及后续工具校正说明；[源码与方法核查](源码与方法核查.md)链接固定源码。完整f32、IDs/config/meta、设备状态、日志、历史诊断可执行文件及退出码均保留；analysis从原始字节重算，不混用失败或排除会话。`verification-summary.json`只声明实际完成的功能/完整性核验；数值初筛仍失败、未定位全部误差、不存在已确认实现缺陷。
