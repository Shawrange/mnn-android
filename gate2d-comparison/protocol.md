# Gate 2-D 冻结实验协议

目的：固定模型、固定 Token 输入和固定生成数量下比较硬件执行成本。Gate C4 已判定固定资产/配置未达到应用质量要求；本阶段不是产品验收，也不是质量等价任务的加速评估。

1. MNN 3.6.2 commit `7e3c6fb5225d3ccf22807ee641332669df34650d`；模型 revision `34dfccda1187ded6e07ea06426da576b0b793c6b`。CPU/GPU 均使用归档干净库和官方 CLI，配置 Low precision、Low memory、Normal power、async=false、greedy、ignore_eos=true、reuse_kv=false、mmap=false、attention_mode=8、dynamic_option=0。CPU 4 线程；OpenCL 请求参数4，对应运行时模式580，非 GPU 线程数。
2. 三组输入为32或128个 Token ID 16；生成64或256。各后端各负载6个独立进程，共36次正式运行。随机种子20261109；6区组，每区组打乱3负载，同负载CPU/GPU相邻，内部顺序随机。顺序在正式运行前保存、哈希冻结。无按速度删样、无失败样本替换、无自动新增实验。
3. CLI 使用 `-p 0 -n 0 -pg PP,TG -rep 1 -load false`。每进程加载一次，执行一次同负载完整预热及一次测量；预热重置逻辑历史，但可复用已分配内存。CPU调优、加载、GPU首次Kernel编译/调优/缓存成本在测量前或预热内；它们可能继续影响设备状态。不预设一次预热已消除全部状态效应。缓存跨进程复用，记录初始/最终清单；首次创建原始日志永久保留，不清旧缓存冒充冷启动。
4. 原生 Prefill Timer覆盖 `forwardVec(embeds)` 和 `updateContext`，不包括输入embedding及此前准备、采样、加载。Decode Timer累计分词解码/输出串追加、逐步forwardVec和状态更新，排除greedy采样等范围。Benchmark通过async=false完成原生同步，不额外插入同步、回调、Tracing或Profiling。原生Timer为gettimeofday；不是单调时钟。TPS倒算耗时依赖固定生成数量；并非完整TTFT/请求端到端时延。
5. 原生JSON不导出成功运行的实际输出IDs/gen_seq_len，其generate_len为请求值。正式前独立count_probe按相同配置、输入、warmup/重复逻辑核查两后端3负载实际计数、输出IDs数量和KV长度。正式计数依据ignore_eos生成循环、成功状态检查及该功能证据约束，明确保留“无每次直接导出计数”的限制。遇Incomplete sample、无效JSON/配置/权重大小、错误/回退标记、超时或非零退出，标记失败并停止，原始记录不删除。
6. 每次至少间隔15秒；开始前skin≤38°C、电池≤36°C、HAL当前CPU最大温度≤80°C、thermal_status=0。15秒轮询，最长300秒，不满足则停止。USB连接，用户已同意熄屏静置，不改系统、锁频、Root或安全设置。保存前后温度、电池/充电、cpufreq、系统内存、负载和可读取GPU sysfs，读取失败原样保留。前后快照不能代表进程执行中全程状态或建立因果关系。
7. `/system/bin/time -v`记录整个进程wall、Max RSS、faults/context switches。它包括加载/调优/预热/测量/退出；不是单次请求端到端。RSS为进程常驻内存，绝非GPU显存。没有可靠进程PSS或GPU独立显存计数，记null；不增加采样观察进程。主机ADB计时也只作为整个命令时长。
8. 正式前少量Pilot仅检查兼容性。首次Pilot路径元数据问题不影响旧证据，另留纠正说明。一次明确的CLI路径兼容核查足够；若随后GPU出现重复阻塞且无法完成，则不无限排查，记录D并结束。
9. 分析全部运行/失败数。各组n=6报告TPS中位数、min/max、样本标准差/CV；配对同区组同负载的原生阶段时间比 CPU/GPU，>1表示该scope GPU执行成本低。可报告两scope之和但不能称总请求时延。原始计时器scope不同于端到端；不与Gate1历史CPU拼接、不声称P95稳定性，不以输出文本差异推断任务质量变化。
10. 完成36次和必要核查后立即停止推理，整理最终报告、README、面试/简历材料并冻结项目。不开展优化、Kernel Profiling、正式产品GPU性能基线或NPU研究。

冻结文件、时间及哈希见 `freeze.json`。Pilot及功能检查不计入正式样本。
