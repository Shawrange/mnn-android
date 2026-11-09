"""Recheck raw benchmark JSON and summarize independent process samples."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,json,math,re,statistics,sys,uuid
from run_bench import load,save,parse_benchmark,parse_state

ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
def quantile(values,q):
    values=sorted(values);pos=(len(values)-1)*q;i=int(pos);j=min(i+1,len(values)-1)
    return values[i]+(values[j]-values[i])*(pos-i)
def stats(values):
    values=[v for v in values if v is not None and math.isfinite(v)]
    if not values:return None
    mean=statistics.mean(values)
    return {'n':len(values),'mean':mean,'median':statistics.median(values),'min':min(values),'max':max(values),
            'p25':quantile(values,.25),'p75':quantile(values,.75),'std_sample':statistics.stdev(values) if len(values)>1 else None,
            'cv_percent':100*statistics.stdev(values)/mean if len(values)>1 and mean else None,
            'p95':quantile(values,.95) if len(values)>=20 else None,
            'p95_note':'Not reported for n<20; no tail/stability claim' if len(values)<20 else 'Exploratory empirical quantile; limited tail samples'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['pilot','baseline'],required=True);ap.add_argument('--session',help='One explicit result directory; otherwise latest session of selected phase');args=ap.parse_args()
    sessions=sorted(p for p in (ROOT/'results').glob(args.phase+'-*') if p.is_dir())
    if not sessions:raise SystemExit('No matching sessions')
    sessions=[Path(args.session).resolve()] if args.session else [sessions[-1]]
    if any(load(s/'protocol.json')['phase']!=args.phase for s in sessions):raise SystemExit('Phase mismatch')
    samples=[];failures=[];session_records=[];evidence=[]
    for session in sessions:
        protocol=load(session/'protocol.json')
        status=load(session/'session-status.json') if (session/'session-status.json').exists() else {'status':'incomplete'}
        session_records.append({'path':str(session.relative_to(ROOT)),'status':status,'protocol':protocol})
        for path in sorted(session.glob('*/sample.json')):
            row=load(path);row['sample_path']=str(path.relative_to(ROOT))
            row['session']=session.name
            timing=path.parent/'benchmark.stderr.txt'
            if timing.exists():
                timing_text=timing.read_text(encoding='utf-8')
                for field,pattern in [('involuntary_context_switches',r'Involuntary context switches:\s*(\d+)'),('voluntary_context_switches',r'Voluntary context switches:\s*(\d+)'),('process_cpu_user_seconds',r'User time \(s\):\s*([\d.]+)'),('process_cpu_system_seconds',r'System time \(s\):\s*([\d.]+)')]:
                    match=re.search(pattern,timing_text)
                    row[field]=float(match.group(1)) if match else None
            for side in ['before','after']:
                state_raw=path.parent/(side+'.stdout.txt')
                if state_raw.exists():
                    row[side]=dict(row.get(side,{}),**parse_state(state_raw.read_bytes().decode('utf-8',errors='replace')))
                for field in ['skin_c','battery_c','cpu_max_c','thermal_status','mem_available_kib']:
                    row[side+'_'+field]=row.get(side,{}).get(field)
                row[side+'_screen_state']=','.join(row.get(side,{}).get('screen_state',[]))
                for policy in ['policy0','policy6']:
                    for field in ['scaling_cur_freq','scaling_max_freq']:
                        row[side+'_'+policy+'_'+field]=row.get(side,{}).get('policies',{}).get(policy,{}).get(field)
            raw=path.parent/'benchmark.json'
            if row['status']=='success':
                try:
                    derived=parse_benchmark(load(raw),row['prompt_tokens'],row['generated_tokens'],protocol)
                    if row.get('exit_code')!=0:raise ValueError('Nonzero exit in successful sample')
                    for key in ['prefill_tps','decode_tps']:
                        if row.get(key)!=derived[key]:raise ValueError('Stored metric differs from raw JSON')
                    row.update(derived)
                except Exception as error:
                    row['status']='analysis_rejected';row['error']=str(error)
            if row['status']!='success':failures.append({'path':row['sample_path'],'status':row['status'],'error':row.get('error')})
            samples.append(row)
            for artifact in sorted(path.parent.iterdir()):
                if artifact.is_file():
                    evidence.append({'path':str(artifact.relative_to(ROOT)),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()})
    groups=[]
    for pp,tg in [[32,32],[128,64],[512,64],[128,256],[512,256]]:
        all_rows=[s for s in samples if s['prompt_tokens']==pp and s['generated_tokens']==tg]
        good=[s for s in all_rows if s['status']=='success']
        group={'prompt_tokens':pp,'generated_tokens':tg,'attempted':len(all_rows),'successful':len(good),'failed':len(all_rows)-len(good),'sample_paths':[s['sample_path'] for s in good]}
        for metric in ['prefill_tps','decode_tps','prefill_ms_derived','decode_ms_derived','max_rss_kib','whole_process_wall_seconds_device','process_wall_seconds_host','decode_wall_tps_rounded','involuntary_context_switches','voluntary_context_switches','process_cpu_user_seconds','process_cpu_system_seconds']:
            group[metric]=stats([s.get(metric) for s in good])
        for key in ['skin_c','battery_c','cpu_max_c','mem_available_kib']:
            for state in ['before','after']:group[state+'_'+key]=stats([s.get(state,{}).get(key) for s in good])
        group['policy_freqs']={}
        for policy in ['policy0','policy6']:
            group['policy_freqs'][policy]={}
            for field in ['scaling_cur_freq','scaling_max_freq']:
                for state in ['before','after']:
                    vals=[s.get(state,{}).get('policies',{}).get(policy,{}).get(field) for s in good]
                    group['policy_freqs'][policy][state+'_'+field]=stats([float(v) for v in vals if v and v.isdigit()])
        group['descriptive_outliers']=[]
        if len(good)>=4:
            for metric in ['prefill_tps','decode_tps']:
                values=[s[metric] for s in good];q1=quantile(values,.25);q3=quantile(values,.75);iqr=q3-q1
                for s in good:
                    if s[metric]<q1-1.5*iqr or s[metric]>q3+1.5*iqr:group['descriptive_outliers'].append({'metric':metric,'value':s[metric],'path':s['sample_path'],'included_in_summary':True})
        if len(good)>=6:
            half=len(good)//2
            group['first_last_half_mean_change_percent']={metric:100*(statistics.mean(s[metric] for s in good[half:])/statistics.mean(s[metric] for s in good[:half])-1) for metric in ['prefill_tps','decode_tps']}
        groups.append(group)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    output=ROOT/'analysis'/f'{args.phase}-{stamp}';output.mkdir(parents=True,exist_ok=False)
    summary={'phase':args.phase,'sessions':session_records,'session_failures':[s for s in session_records if s['status']['status']!='completed'],'attempted':len(samples),'successful':sum(s['status']=='success' for s in samples),'failures':failures,'groups':groups,
             'method':'Independent process, upstream -rep 1: one discarded warmup plus one measured sample. Linear interpolated quantiles (type 7); sample std n-1; no speed-based exclusions.',
             'limits':['Synthetic token id 16, not natural prompt distribution','No TTFT or PSS measured by benchmark','RSS is whole-process maximum, includes warmup/load/tuning','Frequency/thermal samples are before/after, not per-token traces','Fresh process does not imply OS cold file cache','Effective dynamic_option 0 for <=300 prompt tokens, 8 for 512 under fixed requested -dyo 0']}
    save(output/'summary.json',summary);save(output/'raw-evidence-hashes.json',evidence)
    fields=['session','index','round','prompt_tokens','generated_tokens','status','started_at_utc','ended_at_utc','exit_code','prefill_tps','decode_tps','prefill_ms_derived','decode_ms_derived','max_rss_kib','whole_process_wall_seconds_device','effective_dynamic_option','involuntary_context_switches','voluntary_context_switches','process_cpu_user_seconds','process_cpu_system_seconds','sample_path','error']
    for side in ['before','after']:
        fields += [side+'_'+f for f in ['skin_c','battery_c','cpu_max_c','thermal_status','mem_available_kib','screen_state']]
        fields += [side+'_'+p+'_'+f for p in ['policy0','policy6'] for f in ['scaling_cur_freq','scaling_max_freq']]
    with (output/'samples.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(samples)
    lines=['|负载|有效/尝试|Prefill mean / median / min–max (tok/s)|Decode mean / median / min–max (tok/s)|峰值RSS中位数(MiB)|','|---|---:|---|---|---:|']
    for g in groups:
        def fmt(s):return f'{s["mean"]:.2f} / {s["median"]:.2f} / {s["min"]:.2f}–{s["max"]:.2f}' if s else 'N/A'
        rss=g['max_rss_kib'];lines.append(f'|{g["prompt_tokens"]}+{g["generated_tokens"]}|{g["successful"]}/{g["attempted"]}|{fmt(g["prefill_tps"])}|{fmt(g["decode_tps"])}|{rss["median"]/1024:.2f}|' if rss else f'|{g["prompt_tokens"]}+{g["generated_tokens"]}|{g["successful"]}/{g["attempted"]}|{fmt(g["prefill_tps"])}|{fmt(g["decode_tps"])}|N/A|')
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines));print('Failures:',len(failures));print('Analysis:',output)

if __name__=='__main__':main()
