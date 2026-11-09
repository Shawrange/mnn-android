# Gate2C4｜MNN Android CPU/GPU模型质量验收报告

**工程决策C：当前固定模型资产、关闭Thinking的提示与推理配置，未达到预先冻结的手机离线短文本应用要求。暂不进入GPU性能基线。** 正式100例上CPU成功24%、GPU成功25%，双方共同失败74例，未观察到整体单向GPU质量下降；存在1例CPU正确/GPU错误及2例相反情况，全部可重复。GPU有真实OpenCL模型计算证据，失败不能简单解释为没运行GPU，也不能由文本不同推断GPU更差。

该结论不是“所有Qwen3-0.6B都不具备这些能力”。本轮没有未量化原模型或其他框架golden，无法把共同失败精确拆成原始模型能力、量化资产、模板、关闭Thinking或共同前处理的贡献；只能判断**当前固定实验组和应用契约**不达标。没有据此制造Runtime Bug，没有更换/重新量化模型，也没有开展优化、NPU或GPU性能基线。

## 1. 范围、冻结和门槛

范围是用户可复核的中文离线短文本草稿助手：来信三分类、显式字段JSON抽取、简单格式/过滤指令、短文/基础确定问答；不是医疗/金融等自动决策，也不代表开放聊天质量。

先独立pilot12例（每类3例），两后端各3/12成功。试跑验证了输入IDs、模板、停止和评分管线；格式/内容失败没有被忽略。随后构建100个新输入，每类25例。冻结UTC `2026-11-09T07:57:54.235571+00:00`；正式运行始于UTC `2026-11-09T07:57:54.313907+00:00`。数据、协议、评分器及测试、配置、驱动源与可执行文件的SHA256写入不可覆盖的[freeze.json](freeze.json)，正式后未更改。数据集SHA256 `07f44c4bdc0a5f843a1cf6be72cf1773e05aca34bbfffc8feeb48dc9af440f57`。

每例有唯一ID、完整原文、类别、gold、合法变体、规则、评分方法及canonical参考答案。100个正式输入唯一、与pilot无相同输入；但为人工编写的相关任务族，不能视作真实用户随机样本。构建脚本、数据和评分hash可相互核查。

正式前声明的GPU要求：分类≥23/25，抽取≥22/25，指令≥23/25，问答≥23/25，总成功≥92/100；JSON语法/schema有效≥24/25，正常EOS≥99/100，无运行错误。CPU也按相同目标计算，用于区分共同模型/配置不足。差异保护：GPU−CPU总体≥−4pp、每类≥−8pp、CPU单独正确≤5例，且预定义配对normal95%区间下界≥−10pp。门槛对应需要直接解析输出、避免草稿误路由的简单应用，并非为了让模型通过而选取宽松标准。

以上门槛没有根据结果放宽。指标不采用C1/C2探索性Logits阈值替代任务质量；旧阈值、原始数值与失败永久保留。本轮若满足A，本可基于任务验收进入下一阶段，但实际未满足。

## 2. 固定资产与有效推理配置

MNN3.6.2 commit `7e3c6fb5225d3ccf22807ee641332669df34650d`；Qwen3-0.6B-MNN revision `34dfccda1187ded6e07ea06426da576b0b793c6b`。小米15/SM8750、Android16、普通ADB；原权重SHA256 `953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`。

正式CPU库为Gate0干净归档 `47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e`，GPU为Gate2-C clean库 `4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61`，没有使用C3插桩库。模型/Tokenizer/llm_config/原配置及手机端工具、库、运行配置逐项hash核对；本轮新部署目录隔离，旧证据保护文件数9,665。

正式设置同一system_prompt和同一模型Jinja模板，jinja.context.enable_thinking=false，rendered prompt包含预关闭的think块。Greedy取首个最大值；96生成Token上限、ignore_eos=false；reuse_kv/prompt_cache/async/mmap=false，dynamic_option0、attention_mode8、memory/precision low、power normal。每例独立进程、新Llm，实测initialKV=0；不承接上一问题上下文。CPU4线程；GPU请求4由该版OR64/512成580，是调优/Buffer/RecordBatch模式，**不是GPU4线程**。没有混入High组或事后调参。

两端100例输入IDs与rendered prompt逐例完全相同，完整配置除backend_type外相同。正式prompt长度范围57–98 Token，生成IDs数量范围2–33（含stop）。实际最后stop均为151645，output_ids保留stop，raw_text不含stop。自然结束200/200；没有超时、截断、未完成、空输出或UTF8损坏被删除。每个进程的stdout/stderr/退出码单独保存。

源代码与接口边界见[源码与推理边界](源码与推理边界.md)。独立小工具是为了保存完整IDs与多行原始文本；没有替换MNN生成策略或修改Runtime。

## 3. 正式任务质量和配对结果

主会话 `results\formal-20261109T075754Z-da955a`，冻结100例均保留分母，200个进程均退出0。总体CPU24/100，Wilson95% `[16.7%,33.2%]`；GPU25/100，`[17.5%,34.3%]`。

|类别|独立case数|CPU成功|GPU成功|CPU Wilson95%|GPU Wilson95%|GPU−CPU|共同对/CPU单对/GPU单对/共同错|
|---|---|---|---|---|---|---|---|
|classification|25|9/25|9/25|[20.2%, 55.5%]|[20.2%, 55.5%]|0.0%|9/0/0/16|
|extraction|25|0/25|0/25|[0.0%, 13.3%]|[0.0%, 13.3%]|0.0%|0/0/0/25|
|instruction|25|6/25|7/25|[11.5%, 43.4%]|[14.3%, 47.6%]|4.0%|6/0/1/18|
|qa|25|9/25|9/25|[20.2%, 55.5%]|[20.2%, 55.5%]|0.0%|8/1/1/15|


总体配对：共同正确23、CPU单独正确1、GPU单独正确2、共同错误74。GPU−CPU为+1pp，预声明配对normal95%区间`[-2.4pp,+4.4pp]`；额外保守描述区间约`[-6.1pp,+8.0pp]`。精确McNemar双侧p=1，仅3个不一致成败对，检验能力有限；**不能由不显著宣布两后端等价**，也不能把+1pp称GPU更优。

分类/抽取没有成败discordance，normal差值区间退化为[0,0]只是该估计公式在零样本discordance下的边界，不代表总体差异确定为零；额外描述区间约±16.7pp。各类n=25、Wilson区间较宽；全部区间也依赖逐case近似独立/可交换假设，人工模板相关性使其不能外推真实用户总体。

原文和IDs相同的case均为75/100，文本不同25例，但只有3例任务成败不同。没有用字符串相似率替代质量评分，也没有把词表元素或重复生成当独立case。

## 4. 失败分类、评分审查与可重复个例

自动评分只strip外层空白，不删除分析、标点、代码块或额外字段。JSON要求严格可解析、无重复key、字段集合和类型正确；顺序/JSON空白可不同。冻结评分器的10个正反例测试通过，覆盖类型、布尔/整数、额外/重复key、代码块、截断及退出错误。完整评分源、测试、日志与逐例score均交付。

CPU标记：format_error14、content_error37、parse_failure25；GPU：9、41、25。这里content_error表示**冻结精确匹配失败**，不必然是事实错误，如句号/额外解释也可能进入该标签。解析失败和schema错误、截断、运行错误分别处理；本轮两端25个抽取全部因Markdown代码块导致JSON直接解析失败，schema_error0；其余执行类失败均0。没有静默删除或把内部JSON重新提取后补算成功。

代表性抽取EX001：字段name/count可读，但包含代码围栏，应用的直接JSON解析契约不接受；EX006还把“松柏会议室”截为“松柏”，EX022的GPU把明确电话给为null。说明格式问题严重，同时不能把全部共同失败都归为单纯包装问题。分类的9个咨询均过，而16个投诉/表扬未给正确唯一标签，存在内容/标签遵循问题；指令与问答也有直接内容错误。

三条成败discordance：

|ID|任务|CPU原文|GPU原文|CPU/GPU成功|
|---|---|---|---|---|
|IN006|instruction|mNOP|MNOP|False/True|
|QA022|qa|12|24|True/False|
|QA023|qa|太阳升起的方向是东边。|东|False/True|


以上每例每后端独立复跑2次，全部输出IDs与正式运行逐Token相同，共12次诊断生成；重复不增加n100。QA023的CPU句子包含正确方向，但违反只输出方向的接口要求；GPU“东”为预先列出的合法变体。不能将这个配对差异说成CPU不知道太阳从东方升起。

[review-records.json](analysis/review-records.json)记录代理对10个代表用例的客观规则核查，没有独立人类复核，也没有主分更改。本评估规则可执行，不需要主观人工裁决；正式gold与规则若有实质问题应另建协议，而非重写本轮。

## 5. 固定上下文Logits诊断

按冻结规则，选择QA022、IN006、QA023三个任务成败分歧，补CL010/CL013/CL018三个双方错误但Token不同案例。每例两位置：原prompt末位，以及首次Greedy分歧前的共同Token前缀；共12个位置配对、24次独立CPU/GPU Prefill。前三例首次分歧本来就在位置0，所以两个位置重复同一语义，**不算新增独立证据**。

每次response(prompt_ids+shared_prefix_ids,...,0)全Prefill、新进程initialKV0；两端IDs相同、KV_after等于完整前缀长度、generated=0、Host shape[1,1,151936]/f32/finite及重复读取一致。这样保证相同Token历史/KV语义，但**不保证完整Prefill算术路径与原增量Decode相同**。

|ID/首次分歧序号(0起)|完整模型任务成败CPU/GPU|CPU重放Top1 / margin|GPU重放Top1 / margin|重放与原下一Token一致CPU/GPU|双边高margin≥1|
|---|---|---|---|---|---|
|QA022/0|True/False|16 / 0.609375|17 / 0.546875|True/True|False|
|IN006/0|False/True|76 / 1.84375|44 / 0.265625|True/True|False|
|QA023/0|False/True|101281 / 0.375|67364 / 1.40625|True/True|False|
|CL010/1|False/False|11 / 0.9375|5373 / 0.4375|True/True|False|
|CL013/1|False/False|11 / 0.140625|151645 / 1.65625|False/True|False|
|CL018/1|False/False|5373 / 0.296875|151645 / 0.78125|True/True|False|


CL013在共同首Token后，CPU完整Prefill重放Top1为11（英文逗号），原Decode下一Token为5373（顿号），即12个位置配对中有1个未完整复现原下一Token。保留这一差异，不称“等价Teacher Forcing”。其他位置的Top1与原下一Token一致。重放都比较相同上下文，不在自由生成已经分叉后继续逐元素混比。

预声明双边高margin为两端各自Top1−Top2≥1.0；所选6个首次分歧中没有符合者。IN006只有CPU较高、QA023只有GPU较高，不能由单边margin推断某后端计算错误。QA022的CPU/GPU margin分别0.609375/0.546875，排序翻转对应“12/24”的实际任务差异；这是可重复的个例下降，没有形成总体单向下降证据。

canonical参考答案第一Token的rank/概率（每个输入的初始位置）：

|ID|CPU/GPU canonical参考首Token rank|CPU/GPU该Token概率|
|---|---|---|
|QA022|1/2|0.631084/0.290332|
|IN006|6/3|0.00281156/0.0393652|
|QA023|4/4|0.0526995/0.0413874|
|CL010|4/2|0.000653088/0.00689007|
|CL013|2/2|0.00126099/0.00218002|
|CL018|1118/555|5.17589e-09/1.94591e-08|


参考答案是冻结variants第一项；Tokenizer可能有不同合法切分，如MNOP的canonical首Token是“MN”，实际正确生成可先输出“M”。“东方”是canonical，但“东”也为冻结合法变体。因此单个canonical Token概率不是全部正确答案概率，不能用其rank直接判质量。共有前缀已偏离canonical答案时参考下一Token记N/A，完整Top5、候选字符串、概率和margin保存在[logits-diagnostics.json](analysis/logits-diagnostics.json)，完整Logits原始f32均保留。

## 6. 本轮实际GPU执行证据

使用既有独立profile库，按同一冻结配置运行CL001哨兵，输入/输出IDs均与正式clean GPU该例相同。该诊断不混入100例主分或性能统计。

|实际OpenCL事件标签|数量|
|---|---|
|Convolution0|394|
|flash_attention_prefill|28|
|flash_decode_partial|28|
|flash_decode_reduce|28|
|rearrange_k|28|
|rearrange_v|28|


本次1个非stop生成Token，因而Convolution394=197×(1 Prefill+1 Decode)，28层Attention Prefill及Decode均有实际设备事件。总事件2574，关键事件存在非零时间；源码获取真实enqueue事件的CL_PROFILING_COMMAND_START/END。启用OPENCL_FALLBACK_LOG的编译证据与库哈希可查，未见Creator回退日志。证明主要线性层与Attention确实执行OpenCL计算，**不证明整个进程100%GPU，也不逐case穷尽CPU回退**；Tokenizer、采样等仍可在CPU。正式clean与诊断的库/同步方式不同，不以profile时间宣称性能或加速。

## 7. 状态、局限和工程决策

正式过程保存前后及每20次进程的设备状态。读取到电池温度范围26.3–30.0°C，skin范围27.3–33.8°C，USB供电；原CPU频率/温度/memory记录保留，不据状态相关性解释数值或质量因果。没有Root或系统安全修改。

局限：只有100个人工短任务、各类25，有模板相关性；无独立原模型质量golden、无其他提示/Thinking/精度组；严格格式要求使语义可读输出也可能失败，这正是预先声明的直接解析应用契约。若未来接受代码围栏剥离或更宽松自然语言答案，必须另设输入/后处理/评分实验组并重新冻结，不能回改本轮主分。CPU正确也不意味着GPU必须逐字一致，反之GPU/CPU共同错误不自动证明Runtime缺陷。

**最终C，不进入独立GPU性能基线。** 两端都远未达到总分/分类/抽取/指令/问答门槛，差异保护虽满足，但它不能替代绝对应用质量。GPU个例可重复失误已保留，当前不足以选择B；并非用CPU低分替GPU开脱，而是按配对数据没有有意义的单向下降。

下一步仅建议重新论证任务范围，或建立独立模型资产/提示/后处理质量实验组，重新冻结并保留本组。不得用替换/重新量化后的模型结果归入本组；本轮不执行这些后续变化、不启动性能优化或NPU。C1/C2探索性Logits失败仍为失败；C3第一Q计算符合预期也不等于全模型任务质量通过。

## 8. 交付与核验

[README](README.md)列原始结果和复现命令；[正式数据集](datasets/formal.jsonl)、[冻结清单](freeze.json)、[评分器](scripts/score.py)、[评分测试](scripts/test_score.py)、[配对原始逐例表](analysis/paired-cases.csv)及数值诊断可直接核查。[verification-summary.json](verification-summary.json)区分“交付完整/运行成功”与“应用质量失败”，不将前者转述为Gate质量通过。
