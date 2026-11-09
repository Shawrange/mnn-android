# Gate 2-A 诊断协议（实验前）

固定 Gate 0 commit/model、CPU4/precision2/memory2/dyo有效0/qa0/fa1/mmap0。
保留 Gate 1 全部文件及干净源码、二进制。只在 diagnostic/decode-gate2a worktree 添加宏保护的观测代码。

公开 getCurrentHistory 能读取 KVMeta::previous；逐次 generate(1) 会改变 API 调用形态；op callback 只能给出整体算子时间。既有 DUMP_PROFILE_INFO 只给聚合数且使用 gettimeofday，因此不足以观察实际扩容。

插桩使用 CLOCK_MONOTONIC，固定大小内存缓冲，退出进程后写 CSV。采集步骤编号、token_id、逻辑 KV 前后值、Attention墙钟、KV alloc/realloc/update墙钟及容量变化事件。Attention包含KV管理，禁止相加重复计入。仅当前同步调用线程记录；用每步 Attention/更新次数及 KV 前后值验证覆盖。记录丢失数，任何丢失或覆盖不符使诊断无效。

步骤墙钟包围既有decode计时段（native Timer创建前到decode_us累加后），不包含采样/历史追加。含微小Timer和插桩开销；另记录调用线程CPU时钟（不含worker）。不称TTFT。缓冲只在AR调用前初始化；热路径无文件/打印/动态容器分配。

先做功能验证：同一个独立public API驱动，clean/diagnostic-off/on各跑合成128→256和自然语言长输出，比较完整greedy token IDs、文本、终态及KV长度。不是全模型数值误差或完整op测试。

之后做pilot验证Trace完整，再做6个区组，每区组clean/off/on × 64/256，128固定输入。每种组合独立进程warmup1+measured1；区组内顺序用固定seed洗牌。最小间隔12秒，沿用Gate1温度窗口；若明显漂移可停止，保留失败与已测数据并说明。

频率/调度低频后台观测对所有模式一致，前后HAL温度/频率/内存状态；无root，不锁频。进程whole-process switches仅混杂线索。Trace on/off同一诊断二进制评估观测开销；clean/off评估编译代码布局等影响。非配对进程差异不解释为因果效应；小样本用中位数和范围，不宣称稳定P95。

正式性能、Trace诊断、功能验证各自目录；原始stdout/stderr/退出码/JSON/CSV/状态全保留。正式结果不覆盖Gate1。根据实际证据最多3个假设，不实现优化。
