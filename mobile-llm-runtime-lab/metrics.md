# 固定版本 Benchmark 指标语义

基准commit：`7e3c6fb5225d3ccf22807ee641332669df34650d`。文件原文和SHA256见`evidence/source/`；以下行号均对应该提交。

## 计时范围

| 指标 | 实际范围 | 不包含/限制 |
|---|---|---|
| `prefill_us` | `llm.cpp:1150–1157`计时`forwardVec(input_embeds)`和`updateContext`；涵盖mask/position构造、模型调度与执行、同步读出、KV更新等该调用内工作 | token输入的embedding在`:1066`先执行，**不在本段计时内**；不含模型load、模板/tokenizer、history初始化以及`:1158`的gc；非TTFT |
| `decode_us` | `speculative_decoding/generate.cpp:86–109`每步tokenizer_decode、追加生成字符串、forwardVec（含本步embedding/图执行/KV操作）、updateContext，随后累加 | 该步`:63`采样、history/output_tokens更新、停止判断位于Timer之前；所以**不含采样**。Benchmark输出stream为null，不含真实UI/终端输出延迟 |
| stdout `decode wall speed (incl. sampling)` | `llm_bench.cpp:1376–1399`：`response`外层wall减prefill_us，再以实际生成token数除该差值 | 差值还含embedding、generate_init、prefill后gc等prefill计时外开销，**不只是纯Decode+采样**；只以两位小数打印，JSON没有该字段 |
| 整进程wall | Android `time -v`的Real time | 包含加载、调优、warmup、有效测量、结果序列化及退出；不是单请求端到端延迟。主机另记ADB命令wall，额外含进程/USB传输开销 |

`forwardRaw`在`llm.cpp:633–650`执行模块、readMap并在async=false时wait；本次CPU同步构建无需推测GPU时间。原生`Timer`在Android走`source/core/AutoTime.cpp:36–39,53–56`的`gettimeofday`，不是monotonic clock；主机ADB wall用`perf_counter`。本次没有修改时钟实现，也没有把wallclock对系统校时的潜在敏感性说成已发生故障。

自回归循环先从Prefill logits采样第一个输出token，再对该token执行一次forward以准备下一轮；达到N个输出时最后一次forward仍在计时。因而工具测的是其定义的N步Decode工作，不直接等于用户看到首token后其余N−1个token的流式延迟。

## `-pg`、Warmup与复用

- `llm_bench.cpp:801–803`将`-pg`标记为sharedKv，`:1367–1389`以`pp`个重复token id 16调用一次`response(..., tg)`，Prefill后沿同一KV状态生成。
- 进程内不同重复之间：`buildLLM`在`:1113–1120`设置async=false、greedy、ignore_eos=true、reuse_kv=false。`generate_init`在`llm.cpp:895–910`清历史/计时器并设置移除旧KV；CPU Attention在`:437–450`判断清理/分配或扩容/更新KV，`CPUKVCacheManager::onClear:730–745`清逻辑长度和缓存Tensor引用。
- 因此**同一次response中Prefill→Decode复用KV；不同重复之间不复用历史上下文内容**。这不表示allocator、模型资源、已调优module或OS文件缓存全部冷却。
- 循环`i=0..nRepeat`，`:1385`只保存i>0；`-rep 1`=1个warmup+1个有效样本。本项目每个独立进程只取1个有效样本，避免上游JSON丢失重复级原始数组。
- load/tuning在循环前，`-load false`不计load；`-load true`的loading_time是同进程三次load的均值，不是严格清除页缓存后的冷启动。
- 该资产未显式设置`chunk`、`kvcache_mmap`、`use_cached_mmap`：源码默认分别为0、false、true。`use_mmap=false`不等于所有缓存禁用；`llm.cpp:201–221`仍设置USE_CACHED_MMAP hint，但不设置EXTERNAL_WEIGHT_DIR，CPU也不走`:230–232`的非CPU shader cache。这里记录的是源码默认/调用规则，不据此声称本次实际发生了磁盘权重映射或缓存命中。
- 固定`-p 0 -n 0`，防止`-pg`之外默认pp512/tg128也执行。

## JSON计算与固定配置边界

`llm_bench.cpp:224–234`：逐样本Prefill TPS=`pp×10^6/prefill_us`；Decode TPS=`context.gen_seq_len×10^6/decode_us`。`:145–163`对这些TPS取算术均值、样本标准差（n−1）；n<=1标准差输出0。**不是先平均耗时再求倒数**。

`jsonAggregator:510–607`输出模型名、weight文件大小/1024³（字段modelSize，实际GiB）、backend/threads/useMmap/precision/memory/power/quantKv/flashAttention，以及每个result的type、请求长度、TPS均值/标准差。modelSize是磁盘权重文件大小，**不是RSS/PSS/模型运行占用**。JSON没有逐重复原始计时数组、实际gen_seq_len、TTFT、RSS/PSS、peak、逐token延迟和dynamic_option。公共头从第一个instance取值，本项目因此一次只跑一个负载与配置。

本项目`-rep 1`下可以从单样本TPS反算`pp/TPS×1000`和`tg/TPS×1000`得到**派生阶段毫秒数**；原始JSON仍完整保留，CSV明确使用`*_ms_derived`名称，不称为工具直接导出的latency。Decode反算使用请求tg，依据该版本greedy+ignore_eos的MAX_TOKENS正常路径；没有独立输出token流做逐token计数审计。

**重要覆盖规则**：`buildLLM:1152–1153`实际传入`promptLen<=300且非0 ? requested%8 : requested%8+8`。固定`-dyo 0`下32/128输入有效0，512输入有效8。CLI参数固定，但有效Runtime模式随长度变；对512与128的差异不能未经控制地只归因于token数/KV长度。本次不为统一该模式修改上游源码。

## 内存与TTFT的可测性

- 官方llm_bench没有直接输出TTFT、RSS、PSS或峰值内存。
- 主实验用Android Toybox `time -v`的Max RSS(KiB)，通过子进程资源统计获取整个进程的高水位；无持续采样线程。它覆盖load/tuning/warmup/有效执行，不能分配到Prefill或Decode阶段，不能当KV独占量。
- `/proc/meminfo`的MemAvailable是全系统快照，不是目标进程RSS。频率和温度为运行前/后读取，不是计时区间内平均或每token状态。
- PSS如需读取，应另开诊断进程采样`/proc/<pid>/smaps_rollup`或`dumpsys meminfo <pid>`，记录权限/开销。该类采样的最大值仅是**采样峰值下界**，与MaxRSS不同；不得混入无轮询基线。
- 主运行器将TTFT/PSS设为null；独立内存诊断如读取成功则单独提供PSS样本。要测热模型请求级TTFT，可在独立C++ harness中以monotonic clock记录response调用前和首次非空输出回调，模型加载在区间外，另记模板/Tokenizer是否包含；本次没有实现或虚构该值。不能用进程首字节或Prefill吞吐冒充TTFT。
