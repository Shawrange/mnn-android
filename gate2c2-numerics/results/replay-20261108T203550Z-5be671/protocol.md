# Gate2-C2 预先固定的诊断协议

只定位数值差异；不测性能、不优化、不运行NPU。CPU使用Gate0归档库，GPU使用Gate2-C clean库；模型图、权重及Revision不变。新进程、新工作目录、新cache，不改旧资产。

先核查response(ids, ..., 0)、最后Token Logits索引、同步、host数据类型/布局。两个已有输入：8×token16及固定模板自然语言输入。每配置先一次无采集Prefill预热；随后同一进程两次reuse_kv=false完整Prefill，保存全部输入、配置、Logits与状态。独立进程复验Low重复性。读取同一输出两次验证readMap稳定性。词表元素不是独立请求。

源码确认后比较CPU/OpenCL Low/High。precision改变不改变模型量化权重；CPU High不等于取消动态输入量化。通过实际张量Backend类型、物理存储字节/precision元数据与半精度格点占比核对选项生效。

先用公共debug callback，只复制第一层Norm输入/输出、第一层Q/K/V投影、第一层Attention、第一块末残差、最终Hidden State、最终Norm及词表头输出。回调内在张量生命周期有效时同步复制到独立host缓冲，完成response后落盘；不延迟持有临时Tensor指针。统一为逻辑NCHW host float32，记录原布局、shape、dtype、backend、拷贝/等待状态；必要时逐步增加检查点，不dump全部张量。debug与无debug的完整Logits比较，以评估诊断是否改变数值；这些运行均不是性能基线。

所有有效张量记录relative RMSE=sqrt(sum((b-a)^2)/sum(a^2))、cosine、max/mean abs、范围及finite。Logits额外Top1/Top5、两端Top1/Top2 margin、排序变化。沿用C1探索性阈值：rRMSE≤0.02、cosine≥0.999、abs差≤0.1+0.02*abs(CPU)的比例≥99.9%，同时shape/input一致、全部finite。不得追溯放宽阈值。层级指标用于定位，不把该Logits阈值充当每层官方规范。

若早期投影可疑，优先固定同一输入进行单算子或host高精度重建比较，保留原权重，区分累积的上游差异与本算子差异。额外实验须先记明假设和边界。全部失败保留原始错误与退出码。最终允许A/B/C/D结论，不预设Backend Bug。

## 追加隔离实验（观察第一层Q差异后、运行前声明）

通过Interpreter Tensor Path只执行原图第一层q_proj Convolution，仍加载原始llm.mnn和external weight，不生成或改写模型。把CPU Low回调保存的逻辑NCHW q_input原值作为两后端共同输入，Low/High各做三次执行并保存输入回读与输出；要求回调计算清单只有该Convolution，Backend落点可核查。目的是验证第一层误差在相同输入、无Attention/KV、无后续累积的路径仍存在；不是判定哪个后端正确。再用同一原权重的CPU Memory_High反量化浮点路径作辅助参照（须先核查源码分支与实际输出），不能称绝对golden或性能优化。若不能安全获得有效子路径，就记录失败，不任意改Runtime。
