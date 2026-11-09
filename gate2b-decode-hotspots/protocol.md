# Gate2-B 实验前协议

固定基底/模型revision与Gate2-A相同；CPU4、precision2、memory2、power0、qa0/fa1、mmap0、effective dyo0；128输入，64或256生成。只复用干净Gate0库和CLI，不修改上游或Gate2-A诊断分支。

先检查设备资产；功能实验以独立public API驱动off/detail各执行合成与自然输入256输出，比较完整Token/文本/最终状态。detail只增加debug回调，返回true，不修改tensor，不在热路径写文件。

官方llm_bench --profile是主归因工具：pilot两负载各一次，随后6个区组，每区组off/profile×两负载，seed20261110，24个独立进程，每进程warmup1+有效1。按名称及类型输出PROF TSV；不将名称行和*类型总计重复相加。

官方仅给累计耗时，不能提供单调用分布。最小补充工具op_probe使用公开setDebugCallback，参照官方before/after边界、steady_clock与output wait，预留500000条调用记录，正常退出后写CSV；记录decode步号/算子ID/起始时刻/耗时，首遇名称/shape注册在计时外，warmup建立metadata。检查非嵌套、单调用线程、无丢失及Attention调用数；不把worker并行时间相加。补充2个区组off/detail×两负载，seed20261111，8进程；样本少，只给本次观测分布，不推断尾部稳定。官方profile和补充工具分别评估开销，不能混池。

协议修订：首个功能诊断使用300000条缓冲，实际记录305318条，dropped5318、退出5；模型生成成功但诊断明确失败，原版本/日志已保存。正式采样前将容量增至500000，不改数学计算或测量边界，重新执行全部功能检查。

验证规则修订：第二次功能诊断native退出0、无丢失，但初版解析器错误要求所有纳秒duration严格大于0；低于时钟粒度的小op允许为0。原会话保留为验证失败，改为检查duration非负、时序不重叠、完整调用数；零值保留计入分布，不填充伪精度，再运行完整功能对照。

三类实验（correctness、official性能/归因、detail）独立目录。最短冷却12s，skin<=38、电池<=36、HAL CPU最高<=80°C、thermalstatus0；超限15s复查最多300s。所有模式同一0.5s后台observer，记录monotonic/boottime、可读频率/线程调度，温度为前后HAL快照。不锁频、不绑核、不root。

第一失败立即停，保存stdout/stderr/exit/JSON/命令/时间。无按速度删除。不把native decode减去op sum的残差全部叫调度成本，不从source或设备ISA支持推断精确kernel已执行，不把profile绝对TPS当off性能。

主交付从原始数据生成，最多3个候选；只有具备重复证据、可隔离原因和安全局部验证路径才建议进入源码改进，否则结束当前CPU优化选题、建议后续另立GPU/NPU路径研究。本轮不实施它们。
