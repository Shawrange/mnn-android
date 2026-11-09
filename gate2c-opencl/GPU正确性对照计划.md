# GPU正确性对照计划（C1，不是性能基线）

## 当前最小验证

优先使用固定版本public `Llm::response(ids,...,0)`完成同一输入的Prefill，再通过 `Llm::getOutputs()[0]` 及 `readMap<float>()`取得host端完整logits。此接口在 `llm.cpp:1451–1453` 返回本次生成参数的输出，不以stdout文字代替数值结果。CPU使用归档干净CPU lib，GPU使用新clean OpenCL lib；同一独立驱动、固定模型和配置，CPU的thread_num为4，GPU请求值4由Runtime编码为580。同步模式，固定输入Token列表先比对一致。

本轮只做两个小输入的Prefill数值探针：8个重复token16，以及固定自然语言经相同模板/Tokenizer得到的输入。保存完整input IDs、logits shape/type、float32 LE原始值、SHA256、有限值统计和最终KV逻辑长度。不开展重复性能测量，不称全面正确性通过。

**预先声明的探索性筛查判据**（在读取GPU数值之前固定；不依据本次结果放宽）：

- 输入Token完全一致，输出shape一致且至少包含151936个词表logits；全部finite。
- 相对RMSE `sqrt(sum((gpu-cpu)^2)/sum(cpu^2)) <= 0.02`。
- cosine similarity >= 0.999。
- 满足 `abs(gpu-cpu) <= 0.1 + 0.02*abs(cpu)` 的元素比例 >= 99.9%。同时报告max/mean绝对误差，不用相对误差除以近零值。
- 报告Top1/Top5重叠与CPU top1-top2 margin；Token不一致不自动等同错误，检查其margin与误差是否足以改变排序。Top1完全一致不是不同后端的全输入硬性标准。

这些是针对量化权重/Low精度CPU与GPU不同计算路径的初步筛查门槛，不是MNN官方误差规范或模型质量结论。若失败，原样记录并停止精度通过声明；不会用文本“看起来合理”覆盖失败，也不会改阈值迎合结果。

## 后续进入独立GPU基线前的门禁

1. 扩展固定语料覆盖短/中/长输入、中文/英文、KV跨容量/块边界、不同Token值；分开High/Low precision配置组，先确认固定权重与输出维度。
2. Decode采用同一CPU固定Token序列的teacher forcing，避免自由生成分叉后把不同上下文的logits作逐元素比较；验证public forward/generate状态语义及KV更新，必要时仅在独立诊断工具/分支构建明确的固定前缀接口，不改正常默认行为。
3. 对每一位置保存logits及margin，报告误差分布、finite、TopK、相对RMSE/cosine；按输入/位置计独立样本，不把词表元素当独立请求。依据预定模型质量要求确定正式阈值，保留本轮探索性阈值和结果。
4. 定位偏差时使用现有debug callbacks对选定层输出复制到CPU：先核对layout、dtype、shape与同步；该模式改变执行/同步，不用于性能基线。保留必要的Norm、QKV、Attention、MLP、最终norm/head层作为检查点，避免全量dump内存爆炸。
5. 自由生成用greedy文本作为端到端sanity，允许浮点顺序/精度引起低margin分叉；更广泛质量评测与精度门禁完成后，再建立独立GPU性能基线。

本轮不执行以上扩展矩阵，不要求CPU/GPU在所有输入上逐字节相同，也不声明跨后端数学计算逐位等价。
