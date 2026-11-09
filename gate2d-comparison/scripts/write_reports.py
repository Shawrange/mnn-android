"""Generate final documents from completed, bounded experiment. No device work."""
from run import *
import statistics
def emit(path,text):path.write_text(text.strip()+'\n',encoding='utf-8')
def main():
    q=load(R/'analysis/summary.json');st=load(R/'analysis/device-state-summary.json');assert q['successful']==36 and not q['failed']
    d=R/q['session'];session=load(d/'session-status.json');freeze=load(R/'freeze.json');dep=load(R/'deployment.json')
    table=(R/'analysis/comparison-table.md').read_text(encoding='utf-8').strip()
    pairlines=['|负载|配对n|Prefill CPU/GPU 中位[范围]|Decode CPU/GPU 中位[范围]|两Timer之和 CPU/GPU 中位[范围]|','|---|---:|---|---|---|']
    for x in q['paired_summary']:
        cells=[]
        for k in ['prefill_cpu_over_gpu','decode_cpu_over_gpu','timer_sum_cpu_over_gpu']:
            a=x['ratios'][k];cells.append(f'{a["median"]:.3f} [{a["min"]:.3f},{a["max"]:.3f}]')
        pairlines.append(f'|{x["pp"]}+{x["tg"]}|{x["n"]}|'+ '|'.join(cells)+'|')
    pairtable='\n'.join(pairlines)
    timet=['|负载|后端|Prefill ms中位|Decode ms中位|整进程wall秒中位[范围]|','|---|---|---:|---:|---|']
    for g in q['groups']:
        m=g['metrics'];w=m['process_wall_seconds_device'];timet.append(f'|{g["pp"]}+{g["tg"]}|{g["backend"]}|{m["prefill_ms_derived"]["median"]:.3f}|{m["decode_ms_derived"]["median"]:.3f}|{w["median"]:.3f} [{w["min"]:.3f},{w["max"]:.3f}]|')
    policy=['|policy|cur_freq快照范围kHz|scaling_max_freq快照范围kHz|','|---|---|---|']
    for name,v in st['cpu_policy_snapshots_khz'].items():
        a=v['scaling_cur_freq'];b=v['scaling_max_freq'];policy.append(f'|{name}|{a["min"]:.0f}–{a["max"]:.0f}|{b["min"]:.0f}–{b["max"]:.0f}|')
    skin=st['overall']['skin_c'];battery=st['overall']['battery_c'];cpu=st['overall']['cpu_max_c'];gpu=st['gpu_hal_max_c'];cool=st['cooldown_seconds']
    groups={(g['backend'],g['pp'],g['tg']):g for g in q['groups']}
    def med(b,pp,tg,k):return groups[b,pp,tg]['metrics'][k]['median']
    short=f'128+64：CPU Prefill/Decode {med("cpu",128,64,"prefill_tps"):.2f}/{med("cpu",128,64,"decode_tps"):.2f} tok/s，GPU {med("opencl",128,64,"prefill_tps"):.2f}/{med("opencl",128,64,"decode_tps"):.2f} tok/s'
    assert all(g['metrics']['prefill_tps']['median']>groups['cpu',g['pp'],g['tg']]['metrics']['prefill_tps']['median'] for g in q['groups'] if g['backend']=='opencl')
    assert all(g['metrics']['decode_tps']['median']<groups['cpu',g['pp'],g['tg']]['metrics']['decode_tps']['median'] for g in q['groups'] if g['backend']=='opencl')
    # Preserve all directions per block, including any crossing in combined timer scopes.
    directions=[]
    for x in q['paired_summary']:
        ps=[p for p in q['pairs'] if (p['pp'],p['tg'])==(x['pp'],x['tg'])]
        directions.append(f'- {x["pp"]}+{x["tg"]}：Prefill GPU成本较低 {sum(p["prefill_cpu_over_gpu"]>1 for p in ps)}/6对；Decode CPU成本较低 {sum(p["decode_cpu_over_gpu"]<1 for p in ps)}/6对；两Timer之和GPU成本较低 {sum(p["timer_sum_cpu_over_gpu"]>1 for p in ps)}/6对。')
    pilot=R/freeze['successful_pilot'];coldreview=load(R/'evidence/path-compatibility/pilot-review.json');cold=R/coldreview['session'];coldsample=load(sorted(cold.glob('*/sample.json'))[0]);warmsample=load(sorted(pilot.glob('*/sample.json'))[0])
    report=f'''# Gate 2-D｜MNN Android CPU/GPU最终性能对照报告

**完成36/36次预定正式运行，全部退出0，无失败替补、无追加性能实验。结果同时支持A和B：OpenCL在这三组负载的原生Prefill scope成本较低，CPU在Decode scope成本较低。项目到此冻结，不进入源码优化或新的GPU/NPU研究。**

这只比较固定输入/生成Token数量下的硬件执行成本。Gate2-C4已判定当前固定模型/关闭Thinking应用配置不达标，该结论继续有效；本轮不是质量等价任务的性能收益，更不是产品级性能验收。{short}。单scope、配对和设备状态边界如下。

## 1. 固定实验组与正式前冻结

- MNN3.6.2 commit `{C['mnn_commit']}`，模型revision `{C['model_revision']}`，小米15/SM8750/Adreno830/Android16。
- CPU使用Gate0归档clean库，GPU使用Gate2-C clean库，CLI两端相同。没有重编译Runtime，没有Tracing/Profile宏、`--profile`、debug callback或额外同步。
- CPU4线程；GPU `-t 4`经源码成为模式580=Wide tuning4|Buffer64|RecordBatch512请求，不是GPU线程数。录制队列实际启用仍依赖驱动能力；本轮没有为正式样本插入事件采集。
- 两端Low precision、Low memory、Normal power、greedy、ignore_eos、async=false、reuse_kv=false、mmap=false；requested dyo0，三负载effective dyo均0；qa0/fa1→attention_mode8。相同权重、Tokenizer、llm_config。原始Token输入为32或128个ID16，无聊天模板/Thinking提示的真实问答语义。
- 协议冻结UTC `{freeze['frozen_at_utc']}`，正式开始 `{session['started_at_utc']}`，结束 `{session['ended_at_utc']}`；所有哈希在[freeze.json](freeze.json)。6区组，每区组打乱3负载，同负载两后端相邻并随机顺序，seed20261109；18对、36独立进程。
- [源码与指标边界](源码与指标边界.md)给出真实函数/行号；[protocol.md](protocol.md)保留正式前声明。

## 2. Pilot、加载、Kernel缓存与warmup

最初Pilot共3进程完成推理，但CLI `-m config.json`使模型大小元数据错误（路径无斜杠，文件大小返回异常值）。全部原始记录保留，独立[pilot-review.json](evidence/path-compatibility/pilot-review.json)明确判定不能用于比较；原记录中的success只代表当时runner未识别此元数据问题，不作为最终有效Pilot。一次范围明确的源码核查定位`getDirectoryOf`，改为`./config.json`，在新部署目录symlink至原权重，未修改源码/模型。修正后3/3 Pilot元数据与执行均成功；这些均不混入36次。

新GPU工作目录起初没有MNN cache；首次原始stdout保留`Can't open file:tmp/mnn_cachefile.bin`和`Update cache ... size=707228`，结束后cache文件归档。首次32+64整进程wall为{coldsample['process_wall_seconds_device']:.3f}s，修正路径后的同负载Pilot为{warmsample['process_wall_seconds_device']:.3f}s。首次记录模型大小无效且两次状态/页缓存也不同，**差值不能认定为纯Kernel编译耗时**。没有单独导出load/compile/tuning各自时间，缺失即缺失；只保留初次准备生命周期及cache变化。首次没有MNN磁盘cache也不代表驱动所有缓存冷。

`-load false`只load一次，CPU `tuning_prepare`在计时前，OpenCL `Llm::tuning`直接返回。`-rep 1`在同一进程执行1次完整同负载warmup，再1次测量；warmup不入JSON。正式跨进程复用本轮缓存，保持同一机制，不清页缓存/系统缓存，不称严格冷启动或完美锁频稳态。一次warmup不能证明彻底排除全部编译/准备效应。

## 3. 请求配置、实际长度和模型状态核查

先使用独立公共API count_probe，链接相同clean库、相同配置与输入，仿照官方调优与OpenCL switchMode，每后端3负载×2连续response。12次功能请求均直接核对 `gen_seq_len == output_ids.size() == requested`、最终KV=pp+tg，状态MAX_TOKENS_FINISHED；首次及后续请求均符合。完整有效配置、输入/输出IDs保留在 `{freeze['functional_session']}`。CPU/GPU六对功能输出IDs均不同，不能视作相同答案质量。

正式CLI原生JSON的generate_len为**请求值**，实际count仅用于其内部TPS分子，成功时不导出output IDs/gen_seq_len。36次均无Incomplete sample/执行错误，配置与固定ignore_eos生成循环相符，count_probe提供独立直接佐证；**仍没有每个正式进程直接导出的实际count，不能假称逐次读取验证了它**。此工具界限永久保留。若要求每次成功count直接留档，需要另行扩展CLI输出；本项目按用户固定干净CLI的边界结束，没有为此改Runtime或补跑样本。

每次原生JSON均CPU/OPENCL、t字段4、precision2、memory2、power0、qa0/fa1、mmapfalse、唯一正确pp/tg，模型权重大小429.93MiB。模型初始化错误、无效JSON、非零退出、回退/错误标记均导致失败并停止。最终36/36成功，0失败，六cell各6；原始JSON未改写。正式过程中未直接读取Llm dump_config，由冻结配置/CLI映射源码/功能dump共同核查有效选项，不把请求字段当作设备实测计数。

## 4. 主要结果

单位tok/s。范围为6个独立进程min/max，CV为n−1样本标准差/均值。更多mean、SD、MAD见[summary.json](analysis/summary.json)，没有P95稳定性或SLA声明。

{table}

CPU Prefill的CV为19.50%–22.13%，明显大于GPU的0.29%–0.37%。CPU出现三次较高TPS：32+64区组3为574.19、128+64区组6为528.46、128+256区组2为541.04，均保留，不按速度剔除；同组其他CPU样本多为约334–371 tok/s。有效dynamic_option相同，现有频率/温度快照不足以解释这些进程差异，不能包装成Runtime模式变化、Bug或因果归因。

RSS是进程Max RSS；不能把OpenCL RSS较低解读为总GPU内存占用较低，驱动共享/映射分配记账不同，未测GPU显存/PSS。

派生阶段毫秒是单样本Token数/TPS×1000，再在6个进程上取中位数；未把中位TPS的倒数冒充中位阶段时间。原生rep1的std0表示单个有效观察，绝不表示设备稳定。

{chr(10).join(timet)}

整进程wall包括load、tuning、warmup、测量、退出；**不是单请求端到端**。本轮没有可靠单请求E2E和完整TTFT记录，两者为null，没有用这些表推导用户延迟。

## 5. 同区组配对执行时间比

比值=CPU阶段时间/GPU阶段时间；>1意味着该scope GPU成本较低，<1意味着CPU成本较低。两Timer之和只组合被观测scope，排除采样、输入embedding等范围，不能称完整推理时延。配对是相邻新进程，未混入Gate1历史CPU。

{pairtable}

{chr(10).join(directions)}

分阶段优势方向比“GPU整体更快”更准确。原生阶段比较支持局部执行成本判断；对于接近1或跨1的合计结果，应保留设备状态与样本波动边界，不从n6外推普遍排序。完整每区组值见[paired-ratios.csv](analysis/paired-ratios.csv)。不增加样本去追求更有利的结论。

具体而言，32+64和128+256的两Timer之和CPU均为6/6对成本较低；128+64比值中位1.023、范围0.906–1.032，排序跨1，不作稳定整体胜负判断。这些是scope相加的有限成本结果，不是完整端到端延迟。

## 6. 设备、内存与调度状态

每次前后共72个原始状态快照，USB供电均为{st['all_usb_powered']}，电量范围{st['battery_percent_range']}%，屏幕状态{st['screen_states']}，thermal_status为{st['thermal_status_values']}。skin {skin['min']:.1f}–{skin['max']:.1f}°C，battery {battery['min']:.1f}–{battery['max']:.1f}°C，当前HAL CPU最大温度{cpu['min']:.1f}–{cpu['max']:.1f}°C；GPU HAL最大传感器快照{gpu['min']:.1f}–{gpu['max']:.1f}°C。实际冷却{cool['median']:.2f}s中位，范围{cool['min']:.2f}–{cool['max']:.2f}s，额外轮询{st['cooldown_extra_poll_runs']}次运行。没有改系统电源、亲和性、时钟或安全设置。

{chr(10).join(policy)}

这是开始/结束时的CPU频率快照，不能代表整个模型执行区间，不用于声称锁频或建立温度/频率因果。进程context switches/faults均包含加载、预热和测量，原始time -v及[device-state-summary.json](analysis/device-state-summary.json)保留，不把OpenCL进程的切换次数直接解释为Decode调度开销。

普通ADB读取GPU gpuclk/cur_freq/gpubusy在36次before及after返回Permission denied，原始stderr保留；没有绕过权限。没有执行期间GPU频率/利用率/能耗，也没有把全局MemAvailable当进程内存。当前结果只适用于原生调频/调度及这些温度门槛的本次会话。

## 7. 执行路径、产物与可追溯性

clean库与Gate0/C0-C1逐字节相同，CPU SHA256 `47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e`；GPU `4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61`；官方CLI `fd85bf65a75656d023feb9e2ad315f6ee7c6033c8f1591a835e54d2985db4676`。权重SHA256 `953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`。

新部署 `{dep['remote']}`；模型只读复用旧目录。设备端/本机模型、配置、库和CLI hash核对，原始ELF/NEEDED及Release CMakeCache/Ninja实际编译命令在evidence。正式构建无GPU_TIME_PROFILE、DUMP_PROFILE_INFO、Gate诊断宏，未调用--profile。OpenCL使用系统vendor驱动，不替换libOpenCL。

实际GPU证据复用C0/C1和C4同一模型、同一后端模式的设备事件：主要线性Convolution与28层Prefill/Decode Attention均有CL START/END事件，诊断无Creator回退日志。此次clean Benchmark新cache和无执行错误提供补充佐证。**没有对正式36次逐算子采事件，不宣称整个进程100%GPU，也不声称排除了每个算子的所有CPU回退**。Tokenizer、采样等Host工作本就位于CPU；不能仅凭配置字符串或文本输出宣布GPU执行。

## 8. 限制、工程决策与停止

1. 三个人工Token负载、单手机/单驱动、每cell n6，不代表真实聊天/长上下文总体；Greedy输出可不同。当前固定应用质量契约失败，任何阶段优势都不能包装成可用产品的加速。
2. 正式输出计数只能由源码约束与独立功能核验支持，未逐次直接导出；原生Timer使用gettimeofday，scope不含完整请求；启动/编译细分、TTFT、请求E2E、PSS、GPU显存、能耗缺失。
3. 未锁频，温度与CPU策略有状态变化；GPU频率权限不足。区组交错减少部分时间漂移，不能消除所有干扰，也不能将跨进程相关性称为因果。
4. 原有C1/C2探索性Logits阈值失败、C3预期量化解释与C4质量失败全部原样保留；这轮成本比较不改变这些结论。

**最终A+B：GPU Prefill、CPU Decode各有执行成本优势；不作“GPU全面加速”或用户体验收益声明。** 完成预定36次后停止所有推理；没有追加Kernel Profiling、源码优化、模型替换或NPU实验。整理根README、FINAL_TECHNICAL_REPORT、INTERVIEW_GUIDE、RESUME_PROJECT，按根PROJECT_FREEZE.json正式冻结。项目成功之处是可复核的工程解释与清晰停止条件，不是强行得到优化补丁。

交付：[samples.csv](analysis/samples.csv)、[原始会话]({q['session'].replace(chr(92),'/')})、[统计程序](scripts/analyze.py)、[状态统计](scripts/summarize_state.py)、[独立核验](scripts/verify.py)、[verification-summary.json](verification-summary.json)。此前17,089原文件逐个hash复核，不修改原始证据。
'''
    emit(R/'Gate2D_CPU_GPU性能对照报告.md',report)
    common=f'''MNN 3.6.2，commit `{C['mnn_commit']}`；Qwen3-0.6B-MNN revision `{C['model_revision']}`。小米15（Snapdragon 8 Elite / Adreno830 / Android16），Windows + WSL2 Ubuntu + Linux NDK r27c / Clang18 / CMake / Ninja / ADB。桌面RTX4060Ti未承担本项目推理实验。'''
    appendix='''|证据主题|报告入口|
|---|---|
|部署、构建和权重来源|[Gate0](gate0/Gate0_执行报告.md)|
|原生指标与CPU重复基线|[Gate1](mobile-llm-runtime-lab/Gate1_性能基线报告.md)|
|逐Token与KV/Attention机制|[Gate2-A](gate2-decode/Gate2_Decode执行机制研究报告.md)|
|算子级热点|[Gate2-B](gate2b-decode-hotspots/Gate2B_Decode热点归因报告.md)|
|驱动/OpenCL真实执行与NPU静态边界|[C0/C1](gate2c-opencl/Gate2C_OpenCL可行性报告.md)|
|跨后端数值定位|[C2](gate2c2-numerics/Gate2C2_CPU_GPU数值差异定位报告.md)|
|独立ARM量化契约复算|[C3](gate2c3-quant/Gate2C3_动态量化数值验证报告.md)|
|冻结任务质量验收|[C4](gate2c4-quality/Gate2C4_模型质量验收报告.md)|
|同会话最终成本比较|[Gate2-D](gate2d-comparison/Gate2D_CPU_GPU性能对照报告.md)|'''
    readme=f'''# MNN Android端侧LLM Runtime执行机制研究

**已完成并冻结。** 在真实Android手机上搭建可复现的CPU/OpenCL推理链路，解释Decode成本和跨后端量化差异，并用冻结任务集检验模型质量。最终没有证据支持必须修改Runtime；固定模型的应用质量未达标，因此只完成有限硬件执行成本比较，不宣称产品可用或优化收益。

## 目标与实际平台

面向端侧推理研发岗位，研究MNN C++ Runtime、CPU Backend、移动GPU执行及工程验证方法。{common}

## 关键工程结果

- 从固定源码构建Android ARM64 Release，归档Linux NDK/Ninja命令、ELF依赖、模型LFS/Git哈希和真机stdout/stderr/退出码；CPU和OpenCL均实际文本生成。
- 建立独立进程随机区组Benchmark工具，分清warmup、共享KV、原生Timer、整进程wall和内存记账。Gate1共50正式CPU样本；最终CPU/GPU对照另取36样本，未拼接历史计算比值。
- 独立诊断分支缓冲逐Token时间，结合源码解释历史KV增长下Attention成本；已有Profiler把主要热点映射为量化线性投影。没有把必要计算包装为Runtime缺陷。
- 通过Adreno OpenCL设备事件验证主要模型计算，保留CPU回退和观测扰动边界。调查Hexagon/QNN仅限静态文档/源码，没有运行NPU。
- 第一层Q隔离、核验真实输入生命周期；独立重建ARMV86 INT8输入与原INT4权重、scale/offset、FMA和FP16后处理，**两输入共43,008元素与CPU Low输出完全一致**，解释约1%–2%浮点差异。不是原始未量化模型黄金验证，也不是Runtime修复。
- 冻结100条四类短任务及确定性评分器，两后端各100进程；CPU24%、GPU25%，共同失败74例。保持原Logits探索性失败和应用质量失败，不事后降阈值。

## 最终CPU/GPU执行特点

{short}。三负载各后端n6，OpenCL Prefill较快、CPU Decode较快；均为同一固定资产和相同Token数量下的原生scope成本，输出内容并不等价。GPU模式580不是GPU线程数。此表不代表完整TTFT、端到端请求延迟或产品质量收益。

{table}

完整范围、CV、配对时间比、温度/频率及限制见[最终对照报告](gate2d-comparison/Gate2D_CPU_GPU性能对照报告.md)。RSS是进程内存，不是GPU显存。

## 可复现的工具与证据

代码按实验职责保留：构建/部署、Benchmark采集、单调时钟缓冲Tracing、公共API算子/张量诊断、独立量化参照、冻结数据集与评分、离线统计和完整性核验。它们是本研究的实验工具，不是通用生产框架。诊断补丁仅在独立worktree，clean正式库与固定上游源码保留。

在Python标准库环境离线复核最终数据，不需要手机、不增加实验：

```powershell
python -B E:/DUANCE/gate2d-comparison/scripts/test_analysis.py
python -B E:/DUANCE/gate2d-comparison/scripts/analyze.py
python -B E:/DUANCE/gate2d-comparison/scripts/verify.py
python -B E:/DUANCE/verify_project.py
```

构建复现先看Gate0的实际configure/build日志和模型锁；GPU增量选项见C0/C1。各Gate README给出对应脚本和环境。本机WSL源码位于`/home/shawrange/src/MNN-3.6.2`。如在另一环境重跑，应另建副本、部署目录和新session，重新记录设备状态；不删除本归档冻结标记、补写或替换旧样本。性能数值不能保证跨驱动/系统/状态复现到同一绝对值。

## 模型质量限制与最终决策

当前发布量化资产、关闭Thinking提示及严格短文本应用契约不达标；失败含JSON代码围栏、标签/指令遵循和内容问题。100个人工用例不足以外推所有Qwen3模型，也没有独立未量化golden把共同失败分解成模型、量化或提示因素。GPU25%对CPU24%不能证明等价或GPU更优。

**停止当前选题并冻结**：保留可运行CPU/OpenCL实现及可信正、负结果；不提交没有依据的Runtime优化，不扩大诊断，不开展NPU或新的性能实验。未完成产品部署、上游PR或性能修复，不将跨后端成本优势写成自研优化提升。最终状态、文件清单与哈希见[PROJECT_FREEZE.json](PROJECT_FREEZE.json)、[project-manifest.json](project-manifest.json)。

## 阅读入口与附录

先读[最终技术报告](FINAL_TECHNICAL_REPORT.md)，面试准备见[INTERVIEW_GUIDE](INTERVIEW_GUIDE.md)，简历文字见[RESUME_PROJECT](RESUME_PROJECT.md)。下列原阶段报告是保留当时结论的历史附录，后续研究没有覆盖其原始证据。

{appendix}
'''
    emit(R.parent/'README.md',readme)
    technical=f'''# 最终技术报告｜Android端侧LLM Runtime研究

## 最终工程判断

固定模型可以在小米15 CPU和Adreno OpenCL上真实执行；构建、基线、调用链、热点、局部量化数值与任务质量都有原始证据和独立分析工具。未发现值得在当前项目中实现的Runtime修复，固定应用质量验收失败。有限CPU/GPU成本比较完成后停止研究，冻结项目；不以必须有加速或补丁作为成功标准。

{common}

## 1. 可执行、可审计的Android链路

Linux NDK r27c交叉编译ARM64 Android21，Release/C++17/c++_static/ARM82/LOW_MEMORY/TRANSFORMER_FUSE，Ninja构建。核对AArch64、Android PIE、动态依赖和LOAD alignment0x4000；实际手机4KiB页，不声称另一16KiB设备已验证。CPU459构建步骤、OpenCL各625步骤，实际日志及退出码保存。源码tracked clean；诊断worktree隔离。

模型是固定revision预转换发布资产，图/权重LFS SHA256和其余Git blob OID已核对。完整原始export参数/exporter commit未公开，不能声称能从原始checkpoint逐字节重建同一资产。模型图包括28层Attention、196个4bit投影与1个8bit词表头；“4bit模型”不意味着所有线性层同位宽。

## 2. Benchmark契约决定比较边界

`llm_bench -pg`先Prefill指定IDs，再从同一KV生成；reuse_kv=false使下一请求逻辑历史重置。rep1是完整warmup加一个测量，load/tuning在前。effective dynamic_option对短prompt为0、512prompt为8，Gate1因此保留条件差异，最终三组pp32/128则均0。

Prefill计时不含embedding，Decode计时不含sample但含逐步embedding、tokenizer decode、forward、状态维护；N个输出还执行N次forward。原生gettimeofday并非单调时钟，async=false走原生readMap/wait。Timer不是TTFT或用户E2E；`time -v`涵盖加载到退出且RSS不是GPU显存。成功JSON缺少直接count导出，最终通过独立功能count核验补强，但明确保留正式逐次count没有直接留档的限制。

## 3. 从KV机制到算子热点

Gate1的128+64/128+256 Decode中位91.53/85.58 tok/s只是历史会话。Gate2-A在独立分支增加热路径缓冲观测，退出统一写文件，CLOCK_MONOTONIC记录每步及Attention/KV scope；clean/OFF/ON两输入完整输出IDs一致。长生成内首末64步Attention中位0.95→1.70ms/Token，占比8.71→14.28%；KV扩容有局部尖峰但贡献较小。上下文增长需要访问历史K/V符合Attention实现，不能把所有下降都归因KV或跨进程温度。

Gate2-B复用官方Profiler及小型公共API工具：Convolution代表线性投影而不是卷积视觉任务，每Token112个Q/K/V/O、84个MLP投影、1个词表头。诊断callback时间中投影占78.57%–82.82%，说明主要成本类别；Profile开销、嵌套与scope另行核查，没有把诊断占比当clean精确占比，也没有把剩余时间都称Runtime调度。缺乏可验证冗余、PMU/带宽上限证据，不做Kernel优化。

## 4. OpenCL是真实执行而非配置名

普通ADB可访问vendor OpenCL，读取Adreno830/OpenCL3.0/驱动0800.71；独立算术Kernel正确。LLM主要线性层和Attention有设备CL事件，Creator诊断无回退日志；Host Tokenizer、采样、shape管理仍在CPU，不能声称100%GPU。clean与profile库分开，Profile会改变等待/提交行为，不能混作正式性能。

GPU `-t 4`的含义是模式位，请求经过OR64/512成580，Buffer/Wide tuning/RecordBatch；实际录制受driver与Backend判断。Android shell可用也不证明APK namespace/manifest集成已完成。Hexagon直接编程与QNN SDK路径仅静态调查，未下载DSP自定义算子或运行NPU。

## 5. 数值差异为何不等于实现Bug

C1/C2探索性Logits门槛失败永久保留。C2核查公共接口、形状/Host布局、同步、重复性及首执行输入生命周期，将显著差异定位至第一层Q/K/V而非相同入口Norm；同Q输入浮点路径与GPU High接近，CPU Low仍有约1%–2%差异。没有将完整Prefill重放假称为与增量Decode算术路径相同的Teacher Forcing。

C3只研究第一Q：实际ARMV86 w4 FP16执行器，输入每Token1024通道一组，权重每64通道一块。独立重建FP16 absmax、FP32 Q/D与FP16乘法、FCVTAS/SQXTN、INT4 nibble/offset解码、INT32分块点积、FP32 FMA与FP16输出。特别追踪TILE_1尾部FMA顺序；初版独立参照6个尾部不一致经按真实顺序修正后归零，Runtime没有修改。

两种输入共43,008输出元素与CPU Low逐字节一致；独立浮点参照与CPU浮点/GPU High仅约5e−8–7e−7相对差异。43,008是元素数，不是独立请求数；FP64参照仍使用同一量化权重，不是原未量化模型golden。结论限于该路径/两个输入/固定metadata mode，支持预期量化语义，不支持全模型万能正确性证明。

## 6. 应用质量决定是否具备使用价值

独立Pilot后冻结100例、每类25：分类、严格JSON抽取、简单指令、确定短问答。CPU/GPU同一Tokenizer/模板、关闭Thinking、greedy、96上限、自然EOS、每例新进程KV0。200/200正常结束，完整输入/输出IDs与原文保留，确定性评分及10项测试通过。

CPU24/100、GPU25/100，配对共同对23、CPU单对1、GPU单对2、共同错74；分类9/9、抽取0/0、指令6/7、问答9/9。抽取代码围栏违反预先直接JSON契约，不能事后剥除再改主分；也有实际内容错误。三条discordance重复结果一致。差值+1pp不代表GPU优越或等价，只有3对成败分歧、样本人工且相关；结论是固定实验组不满足应用要求，非所有Qwen3模型不行。

代表性Logits比较固定Token历史，新进程全Prefill；保留1个重放与原Decode下一Token不同的记录。不把自由生成分叉后的不同历史Logits混比。C3算子解释成立不等于C4模型质量通过。

## 7. 最终有限硬件成本比较

{short}。以下全部来自本轮36新进程，不与Gate1拼接：

{table}

{pairtable}

分阶段GPU Prefill与CPU Decode各有优势。比值>1表示GPU该scope成本较低；两Timer之和排除其他工作，不能称用户端到端加速。n6只给中位/范围/SD/CV，不作尾部稳定性声明；有状态混杂，普通ADB读取GPU频率/忙碌度权限被拒，未改安全机制。

skin快照{skin['min']:.1f}–{skin['max']:.1f}°C、电池{battery['min']:.1f}–{battery['max']:.1f}°C，CPU频率前后变化保留。首次GPU cache创建与后续warmup分开，未可靠拆出编译耗时。正式输出计数没有直接导出，此限制和功能check依据透明记录。RSS不等于显存。固定生成内容可能不同、质量未过，不能称产品任务加速。

## 8. 工程结案与复核

旧Gate证据不修改。最终核验保护17,089个旧文件，36次正式样本、冻结时间/hash、clean库、原生JSON和统计相互一致；机器可读结果见Gate2-D verification-summary与根project-manifest/PROJECT_FREEZE。离线复核命令见README，构建与真机重现需在新副本使用独立session，不覆盖归档。

本项目交付了部署工具、可追溯实验、可证伪假设和数值参照；没有Runtime加速补丁、上游PR或产品部署。最终停止，不自动开展GPU性能深化、NPU、全模型逐层排查或第二项目。未来如有新需求，应另建范围和资产组，由新任务授权，而非继续扩展本次证据。

## 原阶段附录

{appendix}
'''
    emit(R.parent/'FINAL_TECHNICAL_REPORT.md',technical)
    interview=f'''# 面试指南｜MNN Android端侧推理工程

## 两分钟项目介绍

我以小米15上的MNN C++ Runtime为研究对象，完成固定Qwen3-0.6B量化资产的CPU/OpenCL部署、源码计时核查和可复现实验。首先建立50样本CPU基线，再用独立诊断分支追踪逐Token、Attention与KV成本；发现Decode长序列成本增长部分符合历史KV读取机制，热点主要是量化投影，但没有证据需要修改Runtime。随后证明Adreno主要模型计算真实执行，定位CPU/GPU数值差异，并独立复算第一Q的ARMV86动态输入量化，43,008元素精确一致。最终100例冻结应用评估CPU24%、GPU25%，当前资产不满足应用要求；按约定只完成36次有限执行成本比较后冻结，没有制造加速或Bug修复。

## 需要能够现场解释的问题

1. **你的原创工程贡献是什么？** 固定版本构建/部署与证据链、随机区组采集器、最小缓冲Tracing、公共API检查点和输入生命周期核验、独立量化参照、冻结评分与离线统计。MNN的Kernel和模型不是自己编写，不能说实现了新推理框架。
2. **为什么不同生成长度Decode TPS不同？** 历史KV随步数增长，Attention读取有效K/V；同一长请求的分段观察支持成本增长，扩容有小尖峰。手机热/调度也可能影响，不用跨进程相关性建立因果。看Gate2-A调用链和segments。
3. **Attention外86%–91%是Runtime开销吗？** 不是。后续Profiler定位大量必要线性投影；callback覆盖时间中Convolution投影约79%–83%。剩余scope并非纯调度；没有PMU/roofline证据。
4. **Convolution为什么是LLM热点？** 模型将线性层导出为1×1 Convolution；每Token197投影，112 Q/K/V/O、84 MLP、1 lm_head，词表头为8bit而其余196个4bit。节点名、原图和执行器映射共同确认。
5. **Profiler数据能当正式性能吗？** 不行。callback、Host wait、GPU event/profile宏会改变执行/提交。正确性、诊断和clean性能分别采集，独立比较ON/OFF扰动；不把占比搬成clean精确时间。
6. **怎样证明GPU真的跑了？** 先枚举驱动并执行独立kernel，再收LLM CL START/END事件，Convolution和Attention数量符合前向次数，启用Creator回退日志但未见回退。不是只看backend字符串；Host工作存在，也未对所有正式case逐算子穷尽。
7. **GPU `-t 4`是什么？** 此版LLM OR64/512成为580：Wide tuning4、Buffer64、RecordBatch512请求；不是GPU4线程，录制还需驱动支持。读 `llm.cpp:237`、`:569`。
8. **Low precision与Low memory能否概括成“全部INT8”？** 不能。实际路径依赖CPU核与执行器；本路径FP16输入先动态量化INT8，INT4权重分块、INT32点积、FP32后处理、FP16输出。GPU Low有不同算术路径，所以同权重也不保证逐字节Logits。
9. **为什么独立量化参照可信？** 不调用MNN GEMM/量化函数、不链接libMNN；解析原权重并核对prepared metadata，采集真实执行入口，重建整数输入和scale，明确tile尾部FMA顺序。43,008是两输入元素数；不是全模型或未量化golden证明。
10. **初版6个差异为何没直接报Bug？** 全在13-token输入末Token，追真实TILE_1发现FMA顺序不同；修正主机参照后精确一致。应先验证诊断/参考契约，不能用抽象INT8公式替代真实Kernel。
11. **如何避免失效输入导致假数值结论？** 公共before callback可能在输入物化之前，重用输入可能有生命周期问题；每次重新上传并在真实执行器入口核验。只用入口已验证的样本归因，保留失效早期实验。
12. **Logits误差大就代表GPU质量差吗？** 不一定。任务阈值需要预定义，不能由词表元素多推导大样本。C4 100例paired任务CPU24/GPU25，没有总体单向GPU劣化证据，也不能证明等价。原探索性Logits失败仍保留。
13. **为什么JSON代码围栏判错？** 预先声明应用直接解析JSON，规则冻结在正式前，事后剥围栏会改变应用契约。也存在内容错误，不能把所有低分都归为格式；新后处理应另设实验组。
14. **固定前缀重放是Teacher Forcing吗？** 保证两端Token历史/KV语义相同，但全Prefill与增量Decode可走不同算术路径；已有一个重放下一Token不匹配，不冒充逐步等价TF。
15. **你的最终性能结论？** {short}。三负载n6，GPU Prefill成本低、CPU Decode成本低；没有开发优化，不能称“自研提升X倍”。看同会话配对时间比，不拼历史CPU。
16. **TPS是TTFT吗？** 不是。原生Prefill排除embedding；Decode排除采样并包含部分Host工作，最后生成Token后仍做forward。time -v是整个进程含warmup/load，不是请求E2E。成功CLI JSON只给请求长度，功能probe实测count但正式逐次未直接导出。
17. **RSS为什么GPU小？** 不同Backend内存分配/驱动记账不同，进程RSS不是显存或模型总占用；没有独立GPU内存/能耗、PSS，不能推断总资源优势。
18. **小样本和设备状态怎样处理？** 6区组随机负载、CPU/GPU相邻随机顺序、冷却门槛和原始温度频率、失败显式保留；报告中位/范围/CV，不称P95稳定。GPU频率权限不足，前后CPU快照不等于运行全程，仍有混杂。
19. **为什么最后没有Runtime补丁？** 热点是必要计算且量化语义被独立解释，尚无可安全验证的实现缺陷。为了求职制造源码改动会破坏证据。诊断补丁不是性能/正确性修复，没有上游PR。
20. **为什么停止？** 固定资产应用质量未过，范围有限的执行成本问题已回答；本次36进程后归档冻结。若以后需要产品能力，先另立质量契约/模型资产，而不是持续扩大Profiler或承诺硬件加速。

## 建议现场演示

离线运行根`verify_project.py`；打开Gate2-D原生JSON及对应命令/退出码，解释一个同区组比值；展示C3独立参照与真实INT8/scale及TILE_1差异处理；打开C4冻结时间、失败用例和评分测试。演示不需要追加手机性能实验。

## 如实回答经验边界

主要代码是研究工具和最小插桩，正式Runtime核心未修改；没有新KV架构、Attention优化、NPU真机推理、产品APK上线或上游贡献。原始MNN导出工具参数未知；仅一个手机/驱动、两种单Q输入和100个人工任务，没有通用兼容性/模型质量保证。
'''
    emit(R.parent/'INTERVIEW_GUIDE.md',interview)
    resume=f'''# 简历项目材料｜可证据核验版本

## 项目名称

Android端侧LLM Runtime执行机制与CPU/OpenCL对照研究（个人工程研究项目，已冻结）

## 技术栈

C++ / Python / MNN3.6.2 / Android ARM64 / NDK r27c / CMake / Ninja / ADB / OpenCL / ARMV86量化路径；小米15 Snapdragon8 Elite / Adreno830。固定Qwen3-0.6B-MNN发布量化资产。

## 简历正文建议

- 基于固定MNN源码完成Android ARM64 CPU与Adreno OpenCL真机推理，建立版本/权重锁定、ELF依赖及设备端SHA256核验、原始日志与退出码归档工具。
- 建立随机区组独立进程Benchmark与设备状态记录，完成50组CPU正式样本和36次同会话CPU/GPU有限对照；区分warmup、Prefill/Decode scope、整进程RSS与端到端指标，发现本配置GPU Prefill、CPU Decode分别具备执行成本优势。
- 在独立诊断分支缓冲逐Token/Attention/KV事件，结合现有Profiler将Decode主要热点映射到197个量化线性投影；用源码与受控实验解释KV增长成本，保留观测扰动及设备混杂边界。
- 针对第一Q投影独立实现ARMV86动态INT8输入、INT4权重与FMA/FP16后处理参照，在两固定输入共43,008输出元素上精确复现CPU Low，解释约1%–2%浮点差异，避免误判Backend缺陷。
- 冻结100例短文本任务与确定性评分规则，完成CPU/GPU配对评估及固定前缀Logits诊断；如实记录固定配置成功率24%/25%未达应用门槛，并据证据停止优化、冻结交付。

## 更短版本（三条）

1. 完成MNN Android CPU/OpenCL部署及真实GPU事件验证，构建、模型、二进制与运行证据按哈希归档。
2. 实现随机区组性能采集、最小逐Token观测和独立量化复算，覆盖50组CPU基线、36次CPU/GPU对照及43,008元素精确数值复现。
3. 以100例冻结任务量化质量边界，区分执行成本与应用收益；没有确认需修复的Runtime问题，完成技术报告和可复核工具后冻结项目。

## 面试补充性能口径

{short}，每cell6独立进程。数值是固定输入/生成数下原生Benchmark scope，并非产品级收益、完整TTFT或用户E2E。所有比较来自同会话，不拼历史CPU；不是本人优化带来的提升。

## 明确不应写入简历的内容

不得写“优化MNN使推理提升X倍”“修复ARM量化Bug”“自研KV Cache/Attention Kernel”“适配NPU并加速”“已提交上游PR”“产品成功上线”或“GPU质量验收通过”。没有这些成果。Tracing/采集补丁是诊断工具，不是Runtime优化。43,008元素是两个输入的局部路径验证，不是43,008条评测样本；100例也不代表通用模型质量基准。

## 核验入口

根README、FINAL_TECHNICAL_REPORT、各Gate报告；Gate2-D `analysis/samples.csv`、`analysis/paired-ratios.csv`，C3独立参照及真实输入/metadata，C4 `freeze.json`与逐例评分。完整文件哈希由根`project-manifest.json`和`verify_project.py`核验。
'''
    emit(R.parent/'RESUME_PROJECT.md',resume)
    print('Wrote Gate2-D report and four final root documents from completed data')
if __name__=='__main__':main()
