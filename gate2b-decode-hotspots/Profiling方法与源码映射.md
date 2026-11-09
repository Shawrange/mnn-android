# Profiling方法与源码映射

基底：`7e3c6fb5225d3ccf22807ee641332669df34650d`。下列行号均为该提交原始文件，离线副本在 `evidence/source/`。本阶段不修改上游任何源码，不增加Runtime诊断补丁；Gate2-A诊断分支亦保留原状。

## 1. 实际可用的Profiler

`transformers/llm/engine/tools/llm_bench.cpp:1200–1277` 定义当前实际使用的 `BenchProfile`；`:1327–1340`创建并安装debug callbacks。`--profile`设置enable_debug，`MNN_LLM_BENCH_PROFILE_NAME`存在即打印名称行。当前使用的是该局部结构，不是 `tools/cpp/Profiler.cpp` 的通用Profiler单例。仓库CPU技能文档仍描述旧输出/要求分开prefill和decode，本研究以真实代码为准。

`BenchProfile::before` (`1227–1234`) 在active时，用 `LlmContext::gen_seq_len>0`区分decode，按(type,name)建map项，初次记录输入shape，再取steady_clock起点。`after` (`1235–1244`) 等待outputs完成、取终点、累计totalUs/calls，初次输出shape记录在终点之后。因此：

- 时间包含单个 `Execution::onExecute` 和其worker等待、after中的output wait调用。
- name/type map查找、字符串/首次shape维护和累计统计并未全部包含在单op时间内，但会进入更外层native计时。
- 仅保存累计耗时和调用数，无单调用分位数。每次显示的shape是首次shape，Attention KV长度增长不会可靠反映在该shape列。
- `print` (`1245–1270`) 同时给名称行和 `name=*` 的类型总计；两者不能重复相加。
- 原JSON只保存阶段TPS等，不保存op统计；本研究保存原stdout TSV，`profile.json`只是解析副本。

`main:1367–1389` 对当前 `-pg` 同一response先prefill再decode；i=0是warmup，`profile.active=enableProfile && i>0`使op累计与JSON都只含有效重复。本轮rep1，故每进程有效1次。没有用`-n`的极短KV代替128输入的真实上下文。

## 2. Runtime与计时范围

`Llm::generate(VARP)` (`engine/src/llm.cpp:1150–1158`) 的Prefill Timer包围forwardVec/updateContext，输入embedding在前、gc在后。Decode Timer位于 `engine/src/speculative_decoding/generate.cpp:86–109`，覆盖tokenizer_decode、字符串维护、forwardVec(含当前token embedding)、状态更新；采样/history追加/stop检查在外。N输出会执行N个Decode forward，最后一份logits未再采样。

`Llm::forwardRaw` (`llm.cpp:592–651,708`) 选择module、onForward、readMap/wait、同步KVMeta。图连接为：

```
StaticModule::onForward/_execute
  → Session::runWithCallBack (debug) 或 Session::run (off)
  → Pipeline::executeCallBack 或 execute
  → cmd.execution->onExecute
  → CPU Backend executor
```

源码：`express/module/StaticModule.cpp:783–836`、`source/core/Session.cpp:271–320`、`source/core/Pipeline.cpp:1173–1281`。

debug时每个有info的command在before/after之间执行 (`Pipeline.cpp:1262–1272`)；缺info的command直接执行 (`1254–1260`)。`_copyInputs`、`_enterExecute/_exitExecute`在callback外，`StaticModule::_resize`也在callback外。Native Decode−op sum包含这些工作、Express/embedding、tokenizer/字符串/上下文维护及profiling bookkeeping等，**不能整体标记为线程池、dispatch、allocator或无效开销**。若需独立量化，须另立最小scope，当前未猜分。

## 3. 嵌套与并行

Pipeline按command顺序同步回调；CPU executor可在onExecute内部用ThreadPool并行，callback测的是父调用墙钟，不是各线程CPU时间之和。`CPUAttention.cpp:1469`、`ConvInt8TiledExecutor.cpp:2929–2967`等join位于scope内。不能再乘4线程。

`While`在当前模型不是Python控制流耗时标签。它由 `CPURasterFactory::onCreate` (`CPURaster.cpp:1215–1230`) 创建 `CPULoop`，`CPULoop::onExecute` (`887–1205`) 执行geometry生成的循环、broadcast binary或内部executor，内部可能并行 (`1192–1201`)；其子工作包在While墙钟内，未额外产生Pipeline逐子op统计。当前观察到的While节点如 `/Mul_104_output_0` 是RoPE broadcast乘法。

通用Profiler与BenchProfile都使用单个current/start，不适合任意并发或嵌套callback。补充工具对同一模型记录depth/owner-thread，实际必须nested=foreign=0才接受；该检查不证明所有MNN模型/后端都不会嵌套。Attention内部QK/PV、KV管理不会再与Attention scope重复相加。

## 4. 主要热点映射与证据等级

实际节点名、类型、调用次数与shape来自官方PROF和补充callback。原模型图由独立只读FlatBuffer工具验证并解析，`evidence/model/graph-detailed.tsv`保留量化属性、通道、kernel、external段和输入输出tensor索引。

|语义/实际图节点|Backend C++路径|为何需要|冗余或局部改动的证据边界|
|---|---|---|---|
|MLP线性，`/layers.N/mlp/{gate,up,down}_proj/Linear`，Convolution，84次/Token|`ConvolutionFloatFactory.cpp:143–155`低内存量化分支 → `DenseConvInt8TiledExecutor::onResize` (`ConvInt8TiledExecutor.cpp:1244–1718`) / `onExecute` (`2208–2980`)|每层SwiGLU的两路升维与降维；1×1 Convolution表示线性投影。图中gate/up 1024→3072、down 3072→1024，均4bit|主要时间包含必要矩阵计算；gate/up共享输入仅支持进一步调查重复量化，不证明其占比大|
|Q/K/V/O线性，`/layers.N/self_attn/.../Linear`，Convolution，112次/Token|同一量化executor family|Q 1024→2048、K/V 1024→1024、O 2048→1024；28层均4bit|QKV在原图共享输入索引，源码各executor有独立量化/缓冲。共享或fusion仍需验证量化参数与生命周期，不能只按地址缓存|
|词表头，`/lm/lm_head/Linear`，Convolution，1次/Token|同executor family，按权重bits选择不同GEMM字段 (`ConvInt8TiledExecutor.cpp:1510–1545`)|1024→151936，为每个词表token提供logit；实际量化属性aMaxOrBits=8，不能按4bit计算工作量|节点最慢不代表实现最差；没有PMU/roofline或同shape微基准证据，不能认定带宽饱和或kernel低效|
|Attention，28次/Token|`CPUAttention::onExecute` (`CPUAttention.cpp:366–1558`)，KV manager内部调用|QK/softmax/PV和历史KV管理；当前fa1/qa0|Gate2-A已解释随KV增长的成本；本轮不重复改KV或kernel|
|LayerNorm，113次/Token|`CPULayerNorm::onExecute` (`CPULayerNorm.cpp:70–185`)，内部MNNNorm/MNNNormPacked|输入/attention后及Q/K归一化、最终norm；RMS语义以参数与模型为准|归一化属于必要计算；改变精度、reduction顺序、融合residual有数值风险，未发现重复执行证据|
|Raster，454次/Token|`CPURaster::onResize/onExecute` (`CPURaster.cpp:397,719–740`)|geometry/lower后物化、layout转换、切片/复制等；包括NC布局与投影输入输出整理|454次并不等于454次冗余拷贝；需要读具体regions、alias/layout契约才能删|
|While，112次/Token|同文件CPULoop，见上节|当前主要RoPE广播乘法；父scope包含内部工作|不能把While与被包含的内部binary或线程时间再次相加|
|UnaryOp/BinaryOp/Cast|`CPUUnary::onExecute` (`CPUUnary.cpp:474–550`)、`CPUBinary::onExecute` (`CPUBinary.cpp:84`)、Cast对应转换路径见CPUCast.cpp|旋转位置编码的Neg/Cos/Sin、MLP激活/乘法、残差及整数/float转换等|图语义及layout相关。小op密集有融合调查价值，但时间小、callback成本敏感，未验证可安全删除|

**路径证明边界**：JSON与构建证明CPU配置，stdout实际报告fp16/i8sdot/i8mm能力，model graph证明1×1量化Convolution及bits；`CPUBackend.cpp:329–335`按fp16能力/Low创建Arm82Backend，`Arm82Backend.cpp:27–59`委托CPU creators；factory的固定条件限定低内存DenseConvInt8 family。`Arm82Functions.cpp:3324–3335`继承int8函数表，executor在resize拷贝函数表。**没有采集每次kernel指针/指令级采样，所以不把这些证据升级为“精确某个ARM86汇编符号已被计时”**。也没有将硬件i8mm支持等同所有op使用i8mm。

## 5. 单调用补充工具与开销比较

`scripts/op_probe.cpp`仅调用既有public API和setDebugCallback，不链接Gate2-A修改库；off/detail两模式共享同一工具、同一干净lib。detail按官方计时边界输出每次调用，预留500000条记录，稳态不写文件、不扩展记录缓冲；warmup登记metadata，正常退出后统一写CSV。首遇metadata若仍在有效阶段，会记录new_metadata_measured，不静默忽略其影响。

以完整Token/文本/最终状态做独立功能验证；这不是全面数值回归。明示buffer溢出/负时间/嵌套/跨线程/调用缺失为无效；零duration只表示两次时钟读数相同，按测量粒度限制处理并原样进入分布，不填造更细耗时。

开销必须分别比较：官方同二进制off/profile（含enable_debug执行路径变化）和补充同工具off/detail。比较同区组、同生成长度的native时间及response wall proxy；两种工具不混池。raw单调用P95只是同一诊断进程中该节点的描述性分位数；跨独立进程才是重复实验，不把几万次callback当作几万个独立设备样本。

后台observer对所有组一致，另有开销但未独立量化。它用CLOCK_MONOTONIC/BOOTTIME的同次读取消除Gate2-A未对齐时钟的问题；频率/调度仍是约0.5秒加读取开销的粗采样，不是每个op的硬件驻留测量。
