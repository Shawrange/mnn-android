# Gate2-C4 质量评估协议 v1

## 场景与预先门槛（试跑前声明，正式冻结时一并锁定）

手机离线中文短文本草稿助手：将明确的来信分为咨询/投诉/表扬，抽取原文明确字段为JSON，执行短小格式/排序/过滤指令，根据给定短文或基础确定知识回答简短问题。用户可复核草稿，不用于医疗/金融等高风险自动决定。不评估开放创作、复杂推理、长上下文、工具调用或知识时效性。

独立pilot 12例（每类3例），只验证工具、分词、模板、停止、格式、评分器；不计正式质量。随后正式100例，每类25例，全部新输入，唯一ID、原文、类别、gold/合法变体、可执行评分规则都冻结。人工编写有意覆盖不同表述，但不是随机抽样基准，可能存在模板相关性。100条仅作此应用范围的工程验收，不外推真实用户总体质量。

GPU须同时满足：分类≥23/25=92%；抽取≥22/25=88%；指令≥23/25；问答≥23/25；总分≥92/100；结构化抽取JSON语法/schema有效≥24/25；完成/自然EOS≥99/100；不得有进程崩溃/运行错误。CPU同样计算这些目标，以区分模型能力不足与后端问题。要求服务端解析和简单决策可靠，抽取因缺失字段/类型约束略宽但仍须用户复核。

允许GPU−CPU实测成功率差总体≥−4个百分点、每类≥−8个百分点（每类至多净少2例），CPU正确/GPU错误≤5/100。额外报告配对区间：以−1/0/+1的逐case差，双侧95% normal paired CI（保守截到[-1,1]），下界须≥−10个百分点才允许A；这不是预先功效充分的人群非劣效研究。每后端成功率给Wilson95%区间，各类n25区间会宽，不只报点估计。精确McNemar双侧p辅助描述配对不对称，不用不显著代替相同。

A：GPU所有质量、稳定性、差异保护及区间门槛满足→可进入独立GPU性能基线，原Logits探索阈值不再作为质量硬门禁。
B：CPU达标且GPU失败，存在≥5/100净成功率下降、或≥3/25某类下降，并且discordance针对性复跑确认；需要针对任务/精度定位，不直接判Runtime Bug。
C：CPU和GPU均不满足这些应用目标，且未满足B所需的有意义下降证据→当前模型/固定提示配置未达到应用要求，应重新定义范围或另设模型资产实验组。
D：数据/评分/KV/设备执行证据无效或不足，或其余不能明确分类的边缘情况。不得靠补样直到通过。最多复跑6个代表性discordance（每后端2次）验证可重复性，重复不算新case。

## 推理固定条件

原模型、Tokenizer、Qwen3 Jinja聊天模板与Revision相同。固定system_prompt，enable_thinking=false（固定版真实接口为jinja.context，不使用其他版本的chat_template_kwargs）；greedy首个最大值，max_new_tokens=96，ignore_eos=false。自然stop token保留在output_token_ids，生成文本不包含stop。每例独立进程/新LLM，KV历史初始0；reuse_kv/prompt_cache/async/mmap=false，dynamic_option0、attention_mode8、memory低、precision低、power normal。CPU线程4；GPU请求4→有效模式580（调优/Buffer/RecordBatch位，不是GPU4线程）。两后端输入IDs须逐例相同。独立新部署目录；同后端可复用本阶段tuning cache，记录缓存状态，绝不复用旧实验可写目录。

本轮所有正式数据只比较CPU Low与GPU Low；不根据结果改precision/提示/Token预算或模型。GPU已有OpenCL后端构建，本阶段另用事件诊断库运行固定哨兵验证实际模型GPU计算；与clean质量结果分开，不能把profile性能当正式运行性能或据backend字符串声称100%GPU。

## 确定性评分与失败

统一只strip首尾空白，不删除解释、思考段、代码块、标点或额外内容。分类/指令/问答以合法字符串变体精确匹配；抽取要求JSON可解析、无重复key、字段集合和类型严格正确，键顺序/JSON空白可不同。所有用例每题二元成功；抽取可另给字段辅助分，但不得代替题级主分。gold与variants在正式运行前冻结。

自然EOS、输出截断(max_tokens)、空输出、运行错误、JSON解析失败、schema/格式错误、内容错误分别标记，可有多个标记；任何截断/未正常完成不得计成功，哪怕已有正确片段。所有100例保留为分母，不删失败。自动评分器先有正反例单元测试；如人工复核，只记录审查注释，不事后改规则/主分。冻结后发现gold/规则实质缺陷则记录并判协议受损，不悄悄修改。

## Logits辅助分析：正式结果之后，固定上下文重放

按ID顺序选择最多6个首次Greedy分歧：优先最多3个CPU正确/GPU错误，其次最多2个反向，再补双方正确不同文本/双方错误；若不足补共同正确的前两case。选定算法先声明，不按期望结论挑选。每例找到除stop外/含stop的共同输出前缀，构造原输入IDs+相同共同Token前缀，使用独立进程response(prefix,...,0)全Prefill，初始KV0，比较同一末位置Logits；不能用自由生成分叉后的不同上下文冒充teacher forcing。

保存完整Logits、同历史IDs、Top1/Top2 margin、Top5、候选Token字符串、softmax概率。比较原CPU/GPU生成下一Token与重放Top1，若不同明确标注Prefill重放与原Decode执行路径不同；不强称逐步Decode teacher forcing等价。参考答案选择冻结variants第一项，优先用encode(rendered_prompt+reference)并核对原prompt IDs为前缀；只在输出共同前缀也匹配参考答案Token前缀时报告下一参考Token的rank/prob，否则标记N/A。额外在空生成前缀记录第一参考Token的rank/prob。高margin预定义两端Top1−Top2均≥1.0 Logit，并结合客观任务评分解释，不以margin大就认定质量错误。

不更改Runtime，不追溯改变C1/C2 Logits阈值/失败。没有性能优化、正式GPU性能基线或NPU研究。
