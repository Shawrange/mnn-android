# Gate 2候选研究问题（本次不执行）

## 1. 同一负载的Prefill波动由哪些执行阶段和设备状态贡献？

**观察与证据**：正式数据各负载Prefill CV为12.62–24.19%；例如128+64范围290.42–542.29 tok/s。全部样本保留，且有前后温度/频率/负载记录。可按报告关联的samples.csv定位每个高低样本。

原始CPU policy还记录到频率上限变化：policy0为2.4/2.7456GHz，policy6为1.9584/2.2464/2.4384/2.6496GHz；这些是前后快照，不是运行期平均频率。样本032（512+64，181.02 tok/s）整进程有55,502次非自愿上下文切换、0次major fault；计数包含load/warmup，不能定位到Prefill或直接作因果解释。

**可能模块**：llm.cpp的forwardVec/forwardRaw与module复用；source/backend/cpu/ThreadPool.cpp、CPURuntime.cpp；低内存ConvolutionFloatFactory/DenseConvolutionTiledExecutor路径。

**尚属猜测**：DVFS/后台负载、核迁移、ThreadPool状态或首次shape/分配行为都可能贡献；端点频率不能证明运行期间频率，未证实任何Runtime Bug。

**下一步实验**：保持同二进制/模型/线程/有效dynamic模式，扩展独立会话并比较warmup次数；单独诊断构建或外部harness分解embedding、forward、gc与初始化；在权限允许时记录调度/频率时间线。诊断开销与正式测量隔离，不先改kernel。

## 2. Decode随历史KV与生成长度变化的成本有多少，如何排除模式与热状态混杂？

**观察与证据**：128输入下tg64 Decode中位数91.53，tg256为85.58 tok/s，相对变化-6.50%；同属有效dynamic_option=0。512输入则被上游强制为8，不能把跨输入组差异只归因于KV。

**可能模块**：ArGeneration::generate、llm.cpp forwardVec/forwardRaw；CPUAttention.cpp、CPUKVCacheManager.cpp的KV更新、扩容与Attention执行。

**尚属猜测**：更长KV读取、缓存扩容、累计热态、调度状态和统计波动均可能影响；当前只有平均Decode吞吐，没有逐token成本或已确认内存带宽瓶颈。

**下一步实验**：外部C++ harness固定有效模式、相同生成步数，分别预置不同KV长度；按相近热状态交错短段测量，并记录阶段/每token时间与分配事件；另比较相同KV起点而不同持续时长，区分上下文成本与热漂移。本次只提出实验，不实施。

## 3. 整进程峰值RSS为何对当前负载长度不敏感，是否掩盖了运行期内存变化？

**观察与证据**：五负载的整进程MaxRSS中位数范围903.57–903.77 MiB；另有独立RSS/PSS轨迹可查。该高水位覆盖load、tuning、warmup，不是KV独占量。

**可能模块**：llm.cpp load/embedding/generate_init；DiskEmbedding、Module加载与CPU allocator；CPUKVCacheManager分配/清理。

**尚属猜测**：加载/权重转换/预打包瞬时峰值可能支配VmHWM；allocator留存或文件映射也可能改变RSS/PSS。尚未证明重复权重、内存泄漏或无效分配。

**下一步实验**：独立harness在load前后、warmup后、Prefill后、Decode后、reset/释放后打时间标记，结合RSS/PSS、映射分类与allocator计数，区分生命周期峰值、稳态驻留和KV变化；核对是否随多轮持续增长。无需Root，权限缺失时记录不可测边界。
