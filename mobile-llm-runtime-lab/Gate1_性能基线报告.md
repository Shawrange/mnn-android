# Gate 1｜MNN Android端侧LLM可信性能基线

本轮已完成固定CPU配置的可追溯基线采集、源码指标核查和独立内存诊断。**没有修改MNN Runtime源码，没有测试GPU/NPU，没有进行性能优化或开始Gate 2实验。**

**主要限制**：Prefill CV为12.62–24.19%，CPU频率上限也有变化。本轮代表该设备原生电源/调度策略与温度门槛下的初步分布，不是锁频稳态基线；不能将全部方差归因于Runtime。

本报告由`scripts/write_report.py`从`analysis/baseline-20261108T143156-8442118b/summary.json`、正式样本和独立诊断原始记录生成。生成时刻UTC：2026-11-08T14:34:26.122784+00:00；用户时区America/Los_Angeles。

## 1. 版本、资产与实验配置

- MNN 3.6.2 commit：`7e3c6fb5225d3ccf22807ee641332669df34650d`；会话前重新检查HEAD和tracked工作树，未重新编译或改变二进制。
- 模型：Qwen3-0.6B-MNN，revision `34dfccda1187ded6e07ea06426da576b0b793c6b`；模型及设备端二进制/配置哈希与Gate 0资产逐一一致，见会话`verified-assets.json`。模型发布者完整导出参数仍未知，未自行重导出。
- 小米15 / SM8750 / Android 16 API36 / arm64-v8a / 4KiB页；Windows ADB。Linux NDK r27c、CMake 4.2.3、Ninja构建的Release产物；ARM82 ON、SME2/KleidiAI/GPU/NPU OFF、c++_static、SEP_BUILD OFF。构建记录与模型配置已复制到每个会话。
- CPU 4线程、Low precision/memory、power normal、greedy、ignore_eos、async=false、reuse_kv=false、mmap=false、KV不量化、Flash Attention请求开启；CLI固定`-dyo 0`。
- 资产未显式设置的chunk/kvcache_mmap/use_cached_mmap依源码默认分别为0/false/true；权重mmap关闭不等于禁用所有缓存。没有直接缓存命中追踪，不推测实际磁盘映射；详见metrics.md。
- **有效dynamic_option**：32/128输入为0，512输入被上游强制改为8。这是基线配置的重要边界；没有通过改Runtime或换参数消除它。

## 2. 方法与样本计数

- Pilot：五负载各2个独立进程，共10个有效样本；最短冷却5秒，10/10成功。试跑发现Prefill明显波动，故正式测量增至每组10次；Pilot与正式数据不混池。
- 正式：50/50成功，五负载各10个有效样本；10个随机区组，每区组各负载一次，seed=20261108，原始schedule已保存。
- 每次新进程`-rep 1`，上游自动先做1次不计结果的warmup、再记录1个有效样本。独立进程间使用固定模型/配置；不清页缓存，不称严格冷启动或纯热会话。
- 最短冷却15.0秒；新进程前检查当前HAL skin<=38°C、battery<=36°C、CPU最高<=80°C、thermal status=0，超限每15秒复查，最多300秒；不改变频率、调度或安全设置。实际冷却中位数15.34秒，范围15.20–61.17秒，16次需要额外检查。
- stdout/stderr/exit/JSON/命令/开始结束UTC/主机monotonic wall/状态前后快照均保存。会话和每次分析均使用UTC+UUID目录，不覆盖。首次失败即停止，失败样本保留；没有根据速度删点。
- 统计为独立进程样本的算术均值、中位数、线性插值Q25/Q75、min–max和样本CV(n−1)。**每组n=10，不报告P95，不据此声称尾部稳定或达成SLA。**
- 正式会话：`results\baseline-20261108T140723-9efc5f25`；开始 `2026-11-08T14:07:23.636599+00:00`，结束 `2026-11-08T14:31:14.054325+00:00`。

## 3. Prefill与Decode性能

单位tok/s，Q25–Q75表示样本IQR，CV为百分比。所有有效样本均包含在统计中。

### Prefill

|输入+生成|有效/尝试|均值|中位数|Q25–Q75|min–max|CV%|
|---|---:|---:|---:|---|---|---:|
|32+32|10/10|397.10|365.23|360.98–366.21|314.91–558.04|21.33|
|128+64|10/10|395.07|346.94|343.49–471.42|290.42–542.29|24.14|
|512+64|10/10|358.61|365.59|308.16–427.69|181.02–460.15|24.19|
|128+256|10/10|376.03|342.15|304.37–465.94|297.40–478.10|21.38|
|512+256|10/10|332.90|322.30|298.14–365.25|290.30–409.36|12.62|

### Decode

|输入+生成|有效/尝试|均值|中位数|Q25–Q75|min–max|CV%|
|---|---:|---:|---:|---|---|---:|
|32+32|10/10|96.69|97.04|96.90–98.53|90.63–98.99|2.68|
|128+64|10/10|91.26|91.53|88.96–93.94|86.37–95.06|3.33|
|512+64|10/10|78.14|78.17|76.64–79.19|75.51–82.50|2.74|
|128+256|10/10|84.95|85.58|84.56–86.01|79.23–87.17|2.60|
|512+256|10/10|75.64|75.48|73.96–76.98|68.86–81.22|4.81|

### 派生阶段耗时、整进程wall与峰值RSS

|输入+生成|Prefill派生毫秒中位数|Decode派生毫秒中位数|整进程wall秒中位数|MaxRSS MiB中位数[min–max]|
|---|---:|---:|---:|---|
|32+32|87.62|329.76|1.801|903.64 [903.28–904.12]|
|128+64|368.94|699.40|3.069|903.71 [903.13–904.00]|
|512+64|1400.47|818.78|5.445|903.77 [903.28–904.23]|
|128+256|374.21|2991.37|7.704|903.65 [903.27–904.34]|
|512+256|1591.93|3392.14|10.559|903.57 [903.22–904.25]|

### 时间顺序检查

每负载按时间排序，后5个与前5个样本的均值相对变化；用于描述漂移，不据此单独归因热衰减。

|输入+生成|Prefill后半/前半变化%|Decode后半/前半变化%|
|---|---:|---:|
|32+32|-2.60|-1.41|
|128+64|+11.38|-0.41|
|512+64|-12.30|-1.43|
|128+256|-18.51|+0.79|
|512+256|+10.45|-2.46|

派生毫秒为单样本token数/TPS×1000，原JSON未直接输出阶段毫秒。整进程wall含load/tuning/warmup/有效测量/序列化/退出；MaxRSS来自Android time -v，覆盖同一生命周期。两者均不是单请求latency或KV独占内存。

## 4. 指标与源码边界

- Prefill计时在`llm.cpp:1150–1157`，包括forwardVec与updateContext；不包含前面的embedding、Tokenizer/模板、加载和其后的gc。
- Decode计时在`speculative_decoding/generate.cpp:86–109`，包括tokenizer_decode/字符串维护/forwardVec/上下文更新；采样、history/output更新和stop检查在Timer之前。当前没有输出stream，不含UI/终端刷新。
- 生成第一个token来自Prefill logits；N个生成token仍执行N次本循环forward，最后一次准备的logits未再被采样。因此该吞吐不是用户首token后N−1个token的直接流式延迟。
- -pg同一次response中复用Prefill KV；每次重复的generate_init清除上一轮历史逻辑KV。模型/allocator和OS页缓存可能仍热。
- JSON对每次tokens/time求TPS后做算术平均与样本标准差(n−1)，不是总token/总耗时。-rep 1的JSON std=0只是一个有效样本。主机统计独立进程样本，不使用这个0判断稳定性。
- JSON modelSize是权重文件字节/1024³(实际GiB)，不是RSS/PSS。JSON没有逐重复原始耗时、实际token流、TTFT、RSS/PSS或peak字段。
- stdout decode wall speed的分母=response wall−prefill_us，还含embedding/init/gc等prefill计时外工作；不只是Decode+采样，且仅打印两位小数。
- 原生Timer在Android用gettimeofday，非monotonic；主机wall用perf_counter。本次未观察/验证系统校时跳变，不将潜在限制当成已发生Bug。
- TTFT未测，写null；不能用Prefill耗时或进程首字节冒充。详细函数/行号、JSON字段和可选TTFT harness方案见[metrics.md](metrics.md)。

## 5. 温度、频率、系统状态与失败

- 当前HAL皮肤温度°C：运行前后全部快照范围 34.510–38.177。
- 电池温度°C：运行前后全部快照范围 32.900–35.500。
- 当前HAL CPU最高温度°C：运行前后全部快照范围 37.600–78.800。
- 系统MemAvailable KiB：运行前后全部快照范围 7155788.000–8146704.000。
- 运行前Wakefulness计数：`{('Dozing',): 41, ('Awake',): 9}`；用户确认熄屏静置，但框架状态有不同值，不能把所有样本视为完全同一后台条件。USB充电状态保持记录；没有中途拔线改变充电方式。
- CPU policy状态（kHz，运行前后快照）：`{"policy0": {"scaling_max_freq": ["2400000", "2745600"], "cpuinfo_max_freq": ["3532800"], "scaling_cur_freq_min_max": [556800, 2745600]}, "policy6": {"scaling_max_freq": ["1958400", "2246400", "2438400", "2649600"], "cpuinfo_max_freq": ["4320000"], "scaling_cur_freq_min_max": [1017600, 2649600]}}`。当前频率与频率上限分开记录；不据端点推断推理全程平均频率或CPU核归属。
- 所有正式温度查询返回的thermal status：`[0.0]`。使用Current temperatures from HAL区块，不使用Cached temperatures；读取失败字段保留null/退出码，不估算。
- 正式会话失败0、样本失败0。Tukey 1.5×IQR标记7个metric点，全部保留；详见`summary.json`中descriptive_outliers与逐样本CSV。
- Pilot频率派生字段最初未兼容ADB CRLF；原始状态文本完整，修正解析后从原文重算，未改写原始运行输出。已增加CRLF测试，7项解析检查通过。

Tukey标记的7个metric点均保留：32+32的Prefill 552.19、314.91、558.04，以及Decode 93.84、90.63；128+256的Decode 79.23；512+256的Decode 68.86。512+64的最慢Prefill 181.02虽未被该组较宽IQR标记，仍在全部统计中。标记不是错误判定或剔除规则，详细sample_path见summary.json。

## 6. 独立RSS/PSS诊断

诊断目录：`diagnostics/memory-20261108T143158-80264813`，状态`completed`。不与正式采样并发，关联吞吐全部排除在基线外；每负载另跑一个进程，0.5秒轮询/proc/<pid>/status与smaps_rollup。

|输入+生成|快照数(全部/身份确认)|最大观测RSS MiB|最大观测PSS MiB|最大观测VmHWM MiB|
|---|---:|---:|---:|---:|
|32+32|4/4|698.84|549.42|903.52|
|128+64|5/5|878.39|559.43|903.93|
|512+64|9/9|895.04|618.49|903.81|
|128+256|14/14|877.23|600.80|903.25|
|512+256|19/19|714.10|680.21|903.73|

PSS是当前比例分摊内存，RSS是驻留页，二者不同；采样最大值是可观测下界，不是精确连续峰值。VmHWM为读取时的历史RSS高水位，最后一次采样后仍可能变化。没有生命周期/phase标记，不能给每个快照贴Prefill/Decode标签；轮询会干扰进程，所以不使用此处速度评估性能。若读取被拒绝，原始memory-errors.txt与null保留，不Root。

本次五组均可读取PSS，所有51个快照的PID和进程名均确认属于目标llm_bench，memory-errors.txt均为空；未遇到这些指标的权限拒绝。TTFT和精确连续PSS峰值仍未测量。

## 7. Gate 2候选问题

见[Gate2_候选研究问题.md](Gate2_候选研究问题.md)。这些是由数据支持的待验证问题，不是已确认的性能Bug，也没有在本次实施优化。

## 8. 复现与证据

- 原始正式结果：`results\baseline-20261108T140723-9efc5f25`，含每个进程stdout/stderr/exit、benchmark.json、状态原文/派生值、命令与时间戳。
- 分析：`analysis/baseline-20261108T143156-8442118b/samples.csv`、`summary.json`、`raw-evidence-hashes.json`；CSV保留sample_path，可逐条回查。
- 配置`configs/cpu.json`；试跑决策`evidence/measurement-decision.md`；固定源码原文与哈希`evidence/source/`；构建/设备/资产记录在每会话根目录。
- 所有运行和分析使用新建目录，失败不覆盖。`scripts/analyze.py --phase baseline --session <明确会话目录>`重算；报告可用`write_report.py --analysis <分析目录> --memory <诊断目录> --output <新报告路径>`生成。
- 本次只覆盖五个合成token负载、CPU 4线程、一个模型资产/设备/系统与一轮随机区组会话；没有自然prompt分布、多轮聊天、长于512输入、冷缓存启动、功耗或准确率评估。
- 性能数值可复现地采集与分析，不等于硬件状态可严格复原。较大波动仍需研究；不把样本P95、单次最好值或不同运行条件的Gate 0吞吐当优化收益。
