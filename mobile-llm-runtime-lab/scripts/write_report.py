"""Create the requested report directly from checked analysis and raw sample metadata."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,json,statistics
from run_bench import ROOT,load,save,parse_state

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--analysis',required=True);ap.add_argument('--memory',required=True);ap.add_argument('--output',default=str(ROOT/'Gate1_性能基线报告.md'));args=ap.parse_args()
    analysis=Path(args.analysis);summary=load(analysis/'summary.json');memory_dir=Path(args.memory);memory=load(memory_dir/'diagnostic-status.json')
    output=Path(args.output)
    if output.exists():raise SystemExit('Report exists; select a new --output path, do not overwrite')
    if summary['phase']!='baseline' or summary['session_failures'] or summary['failures']:raise SystemExit('Baseline failures must be reviewed before final report')
    if len(summary['sessions'])!=1 or summary['sessions'][0]['status']['status']!='completed':raise SystemExit('Expected one completed session')
    groups=summary['groups'];gmap={(g['prompt_tokens'],g['generated_tokens']):g for g in groups}
    if any(g['successful']<10 for g in groups):raise SystemExit('Insufficient planned samples')
    session=ROOT/summary['sessions'][0]['path'];protocol=load(session/'protocol.json');rows=[]
    for path in sorted(session.glob('*/sample.json')):
        row=load(path)
        if row['status']=='success':
            for side in ['before','after']:
                row[side].update(parse_state((path.parent/(side+'.stdout.txt')).read_bytes().decode('utf-8',errors='replace')))
            rows.append(row)
    rel=lambda p:Path(p).relative_to(ROOT).as_posix()
    states=[row[s] for row in rows for s in ['before','after']]
    limits=lambda key:(min(s[key] for s in states if s.get(key) is not None),max(s[key] for s in states if s.get(key) is not None))
    wake=Counter(tuple(row['before']['screen_state']) for row in rows)
    cool=[row['cooldown']['seconds'] for row in rows]
    extra=sum(row['cooldown']['checks']>1 for row in rows)
    outliers=[dict(o,workload=f'{g["prompt_tokens"]}+{g["generated_tokens"]}') for g in groups for o in g['descriptive_outliers']]
    frequencies={}
    for policy in ['policy0','policy6']:
        frequencies[policy]={field:sorted({s['policies'].get(policy,{}).get(field) for s in states if s['policies'].get(policy,{}).get(field) is not None}) for field in ['scaling_max_freq','cpuinfo_max_freq']}
        current=[int(s['policies'][policy]['scaling_cur_freq']) for s in states if s['policies'].get(policy,{}).get('scaling_cur_freq','').isdigit()]
        frequencies[policy]['scaling_cur_freq_min_max']=[min(current),max(current)] if current else None
    lines=['# Gate 1｜MNN Android端侧LLM可信性能基线',
      '', '本轮已完成固定CPU配置的可追溯基线采集、源码指标核查和独立内存诊断。**没有修改MNN Runtime源码，没有测试GPU/NPU，没有进行性能优化或开始Gate 2实验。**',
      '',f'本报告由`scripts/write_report.py`从`{rel(analysis)}/summary.json`、正式样本和独立诊断原始记录生成。生成时刻UTC：{datetime.now(timezone.utc).isoformat()}；用户时区America/Los_Angeles。',
      '', '## 1. 版本、资产与实验配置','',
      f'- MNN 3.6.2 commit：`{protocol["mnn_commit"]}`；会话前重新检查HEAD和tracked工作树，未重新编译或改变二进制。',
      f'- 模型：Qwen3-0.6B-MNN，revision `{protocol["model_revision"]}`；模型及设备端二进制/配置哈希与Gate 0资产逐一一致，见会话`verified-assets.json`。模型发布者完整导出参数仍未知，未自行重导出。',
      '- 小米15 / SM8750 / Android 16 API36 / arm64-v8a / 4KiB页；Windows ADB。Linux NDK r27c、CMake 4.2.3、Ninja构建的Release产物；ARM82 ON、SME2/KleidiAI/GPU/NPU OFF、c++_static、SEP_BUILD OFF。构建记录与模型配置已复制到每个会话。',
      '- CPU 4线程、Low precision/memory、power normal、greedy、ignore_eos、async=false、reuse_kv=false、mmap=false、KV不量化、Flash Attention请求开启；CLI固定`-dyo 0`。',
      '- 资产未显式设置的chunk/kvcache_mmap/use_cached_mmap依源码默认分别为0/false/true；权重mmap关闭不等于禁用所有缓存。没有直接缓存命中追踪，不推测实际磁盘映射；详见metrics.md。',
      '- **有效dynamic_option**：32/128输入为0，512输入被上游强制改为8。这是基线配置的重要边界；没有通过改Runtime或换参数消除它。',
      '', '## 2. 方法与样本计数','',
      '- Pilot：五负载各2个独立进程，共10个有效样本；最短冷却5秒，10/10成功。试跑发现Prefill明显波动，故正式测量增至每组10次；Pilot与正式数据不混池。',
      f'- 正式：{summary["successful"]}/{summary["attempted"]}成功，五负载各10个有效样本；10个随机区组，每区组各负载一次，seed={protocol["order_seed"]}，原始schedule已保存。',
      '- 每次新进程`-rep 1`，上游自动先做1次不计结果的warmup、再记录1个有效样本。独立进程间使用固定模型/配置；不清页缓存，不称严格冷启动或纯热会话。',
      f'- 最短冷却{protocol["cooldown_seconds"]}秒；新进程前检查当前HAL skin<=38°C、battery<=36°C、CPU最高<=80°C、thermal status=0，超限每15秒复查，最多300秒；不改变频率、调度或安全设置。实际冷却中位数{statistics.median(cool):.2f}秒，范围{min(cool):.2f}–{max(cool):.2f}秒，{extra}次需要额外检查。',
      '- stdout/stderr/exit/JSON/命令/开始结束UTC/主机monotonic wall/状态前后快照均保存。会话和每次分析均使用UTC+UUID目录，不覆盖。首次失败即停止，失败样本保留；没有根据速度删点。',
      '- 统计为独立进程样本的算术均值、中位数、线性插值Q25/Q75、min–max和样本CV(n−1)。**每组n=10，不报告P95，不据此声称尾部稳定或达成SLA。**',
      f'- 正式会话：`{summary["sessions"][0]["path"]}`；开始 `{summary["sessions"][0]["status"]["started_at_utc"]}`，结束 `{summary["sessions"][0]["status"]["ended_at_utc"]}`。',
      '', '## 3. Prefill与Decode性能','', '单位tok/s，Q25–Q75表示样本IQR，CV为百分比。所有有效样本均包含在统计中。','']
    for metric,title in [('prefill_tps','Prefill'),('decode_tps','Decode')]:
        lines += [f'### {title}','', '|输入+生成|有效/尝试|均值|中位数|Q25–Q75|min–max|CV%|','|---|---:|---:|---:|---|---|---:|']
        for g in groups:
            s=g[metric];lines.append(f'|{g["prompt_tokens"]}+{g["generated_tokens"]}|{g["successful"]}/{g["attempted"]}|{s["mean"]:.2f}|{s["median"]:.2f}|{s["p25"]:.2f}–{s["p75"]:.2f}|{s["min"]:.2f}–{s["max"]:.2f}|{s["cv_percent"]:.2f}|')
        lines.append('')
    lines += ['### 派生阶段耗时、整进程wall与峰值RSS','', '|输入+生成|Prefill派生毫秒中位数|Decode派生毫秒中位数|整进程wall秒中位数|MaxRSS MiB中位数[min–max]|','|---|---:|---:|---:|---|']
    for g in groups:
        p=g['prefill_ms_derived'];d=g['decode_ms_derived'];w=g['whole_process_wall_seconds_device'];r=g['max_rss_kib']
        lines.append(f'|{g["prompt_tokens"]}+{g["generated_tokens"]}|{p["median"]:.2f}|{d["median"]:.2f}|{w["median"]:.3f}|{r["median"]/1024:.2f} [{r["min"]/1024:.2f}–{r["max"]/1024:.2f}]|')
    lines += ['', '### 时间顺序检查','', '每负载按时间排序，后5个与前5个样本的均值相对变化；用于描述漂移，不据此单独归因热衰减。','', '|输入+生成|Prefill后半/前半变化%|Decode后半/前半变化%|','|---|---:|---:|']
    for g in groups:
        drift=g.get('first_last_half_mean_change_percent',{})
        lines.append(f'|{g["prompt_tokens"]}+{g["generated_tokens"]}|{drift.get("prefill_tps",float("nan")):+.2f}|{drift.get("decode_tps",float("nan")):+.2f}|')
    lines += ['', '派生毫秒为单样本token数/TPS×1000，原JSON未直接输出阶段毫秒。整进程wall含load/tuning/warmup/有效测量/序列化/退出；MaxRSS来自Android time -v，覆盖同一生命周期。两者均不是单请求latency或KV独占内存。',
      '', '## 4. 指标与源码边界','',
      '- Prefill计时在`llm.cpp:1150–1157`，包括forwardVec与updateContext；不包含前面的embedding、Tokenizer/模板、加载和其后的gc。',
      '- Decode计时在`speculative_decoding/generate.cpp:86–109`，包括tokenizer_decode/字符串维护/forwardVec/上下文更新；采样、history/output更新和stop检查在Timer之前。当前没有输出stream，不含UI/终端刷新。',
      '- 生成第一个token来自Prefill logits；N个生成token仍执行N次本循环forward，最后一次准备的logits未再被采样。因此该吞吐不是用户首token后N−1个token的直接流式延迟。',
      '- -pg同一次response中复用Prefill KV；每次重复的generate_init清除上一轮历史逻辑KV。模型/allocator和OS页缓存可能仍热。',
      '- JSON对每次tokens/time求TPS后做算术平均与样本标准差(n−1)，不是总token/总耗时。-rep 1的JSON std=0只是一个有效样本。主机统计独立进程样本，不使用这个0判断稳定性。',
      '- JSON modelSize是权重文件字节/1024³(实际GiB)，不是RSS/PSS。JSON没有逐重复原始耗时、实际token流、TTFT、RSS/PSS或peak字段。',
      '- stdout decode wall speed的分母=response wall−prefill_us，还含embedding/init/gc等prefill计时外工作；不只是Decode+采样，且仅打印两位小数。',
      '- 原生Timer在Android用gettimeofday，非monotonic；主机wall用perf_counter。本次未观察/验证系统校时跳变，不将潜在限制当成已发生Bug。',
      '- TTFT未测，写null；不能用Prefill耗时或进程首字节冒充。详细函数/行号、JSON字段和可选TTFT harness方案见[metrics.md](metrics.md)。',
      '', '## 5. 温度、频率、系统状态与失败','']
    for key,title in [('skin_c','当前HAL皮肤温度°C'),('battery_c','电池温度°C'),('cpu_max_c','当前HAL CPU最高温度°C'),('mem_available_kib','系统MemAvailable KiB')]:
        lo,hi=limits(key);lines.append(f'- {title}：运行前后全部快照范围 {lo:.3f}–{hi:.3f}。')
    lines += [f'- 运行前Wakefulness计数：`{dict(wake)}`；用户确认熄屏静置，但框架状态有不同值，不能把所有样本视为完全同一后台条件。USB充电状态保持记录；没有中途拔线改变充电方式。',
      f'- CPU policy状态（kHz，运行前后快照）：`{json.dumps(frequencies,ensure_ascii=False)}`。当前频率与频率上限分开记录；不据端点推断推理全程平均频率或CPU核归属。',
      f'- 所有正式温度查询返回的thermal status：`{sorted({s.get("thermal_status") for s in states})}`。使用Current temperatures from HAL区块，不使用Cached temperatures；读取失败字段保留null/退出码，不估算。',
      f'- 正式会话失败{len(summary["session_failures"])}、样本失败{len(summary["failures"])}。Tukey 1.5×IQR标记{len(outliers)}个metric点，全部保留；详见`summary.json`中descriptive_outliers与逐样本CSV。',
      '- Pilot频率派生字段最初未兼容ADB CRLF；原始状态文本完整，修正解析后从原文重算，未改写原始运行输出。已增加CRLF测试，7项解析检查通过。',
      '', '## 6. 独立RSS/PSS诊断','', f'诊断目录：`{rel(memory_dir)}`，状态`{memory["status"]}`。不与正式采样并发，关联吞吐全部排除在基线外；每负载另跑一个进程，0.5秒轮询/proc/<pid>/status与smaps_rollup。','',
      '|输入+生成|快照数(全部/身份确认)|最大观测RSS MiB|最大观测PSS MiB|最大观测VmHWM MiB|','|---|---:|---:|---:|---:|']
    def mb(value):return f'{value/1024:.2f}' if value is not None else '不可用'
    for item in memory['samples']:
        lines.append(f'|{item["prompt_tokens"]}+{item["generated_tokens"]}|{item["sample_count"]}/{item["identity_confirmed_snapshots"]}|{mb(item["max_observed_rss_kib"])}|{mb(item["max_observed_pss_kib"])}|{mb(item["max_observed_vmhwm_kib"])}|')
    lines += ['', 'PSS是当前比例分摊内存，RSS是驻留页，二者不同；采样最大值是可观测下界，不是精确连续峰值。VmHWM为读取时的历史RSS高水位，最后一次采样后仍可能变化。没有生命周期/phase标记，不能给每个快照贴Prefill/Decode标签；轮询会干扰进程，所以不使用此处速度评估性能。若读取被拒绝，原始memory-errors.txt与null保留，不Root。',
      '', '## 7. Gate 2候选问题','', '见[Gate2_候选研究问题.md](Gate2_候选研究问题.md)。这些是由数据支持的待验证问题，不是已确认的性能Bug，也没有在本次实施优化。',
      '', '## 8. 复现与证据','',
      f'- 原始正式结果：`{summary["sessions"][0]["path"]}`，含每个进程stdout/stderr/exit、benchmark.json、状态原文/派生值、命令与时间戳。',
      f'- 分析：`{rel(analysis)}/samples.csv`、`summary.json`、`raw-evidence-hashes.json`；CSV保留sample_path，可逐条回查。',
      '- 配置`configs/cpu.json`；试跑决策`evidence/measurement-decision.md`；固定源码原文与哈希`evidence/source/`；构建/设备/资产记录在每会话根目录。',
      '- 所有运行和分析使用新建目录，失败不覆盖。`scripts/analyze.py --phase baseline --session <明确会话目录>`重算；报告可用`write_report.py --analysis <分析目录> --memory <诊断目录> --output <新报告路径>`生成。',
      '- 本次只覆盖五个合成token负载、CPU 4线程、一个模型资产/设备/系统与一轮随机区组会话；没有自然prompt分布、多轮聊天、长于512输入、冷缓存启动、功耗或准确率评估。',
      '- 性能数值可复现地采集与分析，不等于硬件状态可严格复原。较大波动仍需研究；不把样本P95、单次最好值或不同运行条件的Gate 0吞吐当优化收益。','']
    output.write_text('\n'.join(lines),encoding='utf-8')
    short=gmap[(128,64)];long=gmap[(128,256)];rss=[g['max_rss_kib']['median']/1024 for g in groups]
    delta=100*(long['decode_tps']['median']/short['decode_tps']['median']-1)
    question_lines=['# Gate 2候选研究问题（本次不执行）','',
      '## 1. 同一负载的Prefill波动由哪些执行阶段和设备状态贡献？','',
      f'**观察与证据**：正式数据各负载Prefill CV为{min(g["prefill_tps"]["cv_percent"] for g in groups):.2f}–{max(g["prefill_tps"]["cv_percent"] for g in groups):.2f}%；例如128+64范围{short["prefill_tps"]["min"]:.2f}–{short["prefill_tps"]["max"]:.2f} tok/s。全部样本保留，且有前后温度/频率/负载记录。可按报告关联的samples.csv定位每个高低样本。','',
      '**可能模块**：llm.cpp的forwardVec/forwardRaw与module复用；source/backend/cpu/ThreadPool.cpp、CPURuntime.cpp；低内存ConvolutionFloatFactory/DenseConvolutionTiledExecutor路径。','',
      '**尚属猜测**：DVFS/后台负载、核迁移、ThreadPool状态或首次shape/分配行为都可能贡献；端点频率不能证明运行期间频率，未证实任何Runtime Bug。','',
      '**下一步实验**：保持同二进制/模型/线程/有效dynamic模式，扩展独立会话并比较warmup次数；单独诊断构建或外部harness分解embedding、forward、gc与初始化；在权限允许时记录调度/频率时间线。诊断开销与正式测量隔离，不先改kernel。','',
      '## 2. Decode随历史KV与生成长度变化的成本有多少，如何排除模式与热状态混杂？','',
      f'**观察与证据**：128输入下tg64 Decode中位数{short["decode_tps"]["median"]:.2f}，tg256为{long["decode_tps"]["median"]:.2f} tok/s，相对变化{delta:+.2f}%；同属有效dynamic_option=0。512输入则被上游强制为8，不能把跨输入组差异只归因于KV。','',
      '**可能模块**：ArGeneration::generate、llm.cpp forwardVec/forwardRaw；CPUAttention.cpp、CPUKVCacheManager.cpp的KV更新、扩容与Attention执行。','',
      '**尚属猜测**：更长KV读取、缓存扩容、累计热态、调度状态和统计波动均可能影响；当前只有平均Decode吞吐，没有逐token成本或已确认内存带宽瓶颈。','',
      '**下一步实验**：外部C++ harness固定有效模式、相同生成步数，分别预置不同KV长度；按相近热状态交错短段测量，并记录阶段/每token时间与分配事件；另比较相同KV起点而不同持续时长，区分上下文成本与热漂移。本次只提出实验，不实施。','',
      '## 3. 整进程峰值RSS为何对当前负载长度不敏感，是否掩盖了运行期内存变化？','',
      f'**观察与证据**：五负载的整进程MaxRSS中位数范围{min(rss):.2f}–{max(rss):.2f} MiB；另有独立RSS/PSS轨迹可查。该高水位覆盖load、tuning、warmup，不是KV独占量。','',
      '**可能模块**：llm.cpp load/embedding/generate_init；DiskEmbedding、Module加载与CPU allocator；CPUKVCacheManager分配/清理。','',
      '**尚属猜测**：加载/权重转换/预打包瞬时峰值可能支配VmHWM；allocator留存或文件映射也可能改变RSS/PSS。尚未证明重复权重、内存泄漏或无效分配。','',
      '**下一步实验**：独立harness在load前后、warmup后、Prefill后、Decode后、reset/释放后打时间标记，结合RSS/PSS、映射分类与allocator计数，区分生命周期峰值、稳态驻留和KV变化；核对是否随多轮持续增长。无需Root，权限缺失时记录不可测边界。','']
    candidate=ROOT/'Gate2_候选研究问题.md'
    if candidate.exists():
        candidate=output.with_name(output.stem+'_Gate2候选.md')
        if candidate.exists():raise SystemExit('Candidate output exists; select a new report output name')
        output.write_text(output.read_text(encoding='utf-8').replace('](Gate2_候选研究问题.md)',']('+candidate.name+')'),encoding='utf-8')
    candidate.write_text('\n'.join(question_lines),encoding='utf-8')
    print(output);print(candidate)

if __name__=='__main__':main()
