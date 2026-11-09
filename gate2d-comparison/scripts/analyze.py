"""Offline only. Native JSON supplies TPS; never treats process wall as request E2E."""
from run import *
import csv,statistics,collections
def stats(v):
    n=len(v)
    return {'n':n,'median':statistics.median(v),'min':min(v),'max':max(v),'mean':statistics.mean(v),'sample_sd':statistics.stdev(v) if n>1 else None,'cv_pct':100*statistics.stdev(v)/statistics.mean(v) if n>1 else None,'mad':statistics.median(abs(x-statistics.median(v)) for x in v)}
def aggregate(samples):
    valid=[s for s in samples if s['status']=='success'];groups=[];pairs=[]
    for pp,tg in [(32,64),(128,64),(128,256)]:
        for b in ['cpu','opencl']:
            ss=[s for s in valid if (s['pp'],s['tg'],s['backend'])==(pp,tg,b)]
            groups.append({'pp':pp,'tg':tg,'backend':b,'n':len(ss),'metrics':{k:stats([s[k] for s in ss]) for k in ['prefill_tps','decode_tps','prefill_ms_derived','decode_ms_derived','max_rss_kib','process_wall_seconds_device'] if ss and all(s.get(k) is not None for s in ss)}})
        for block in range(1,7):
            ss={s['backend']:s for s in valid if (s['pp'],s['tg'],s['block'])==(pp,tg,block)}
            if len(ss)!=2:continue
            c,g=ss['cpu'],ss['opencl']
            pairs.append({'pp':pp,'tg':tg,'block':block,'cpu_index':c['index'],'gpu_index':g['index'],
                'prefill_cpu_over_gpu':c['prefill_ms_derived']/g['prefill_ms_derived'],
                'decode_cpu_over_gpu':c['decode_ms_derived']/g['decode_ms_derived'],
                'timer_sum_cpu_over_gpu':(c['prefill_ms_derived']+c['decode_ms_derived'])/(g['prefill_ms_derived']+g['decode_ms_derived'])})
    paired=[]
    for pp,tg in [(32,64),(128,64),(128,256)]:
        ss=[s for s in pairs if (s['pp'],s['tg'])==(pp,tg)]
        paired.append({'pp':pp,'tg':tg,'n':len(ss),'ratios':{k:stats([s[k] for s in ss]) for k in ['prefill_cpu_over_gpu','decode_cpu_over_gpu','timer_sum_cpu_over_gpu'] if ss}})
    return {'attempted':len(samples),'successful':len(valid),'failed':[s for s in samples if s['status']!='success'],'groups':groups,'pairs':pairs,'paired_summary':paired}
def main():
    start=load(R/'FORMAL_STARTED.json');d=R/start['session'];schedule=load(d/'schedule.json');samples=[]
    for path in sorted(d.glob('*/sample.json')):
        s=load(path);s['directory']=str(path.parent.relative_to(R))
        if s['status']=='success':
            derived=parse(load(path.parent/'benchmark.json'),s['backend'],s['pp'],s['tg'])
            for k,v in derived.items():assert s[k]==v,(path,k)
            assert load(path.parent/'benchmark.command.json')['exit_code']==s['exit_code']==0
        samples.append(s)
    result=aggregate(samples);result.update(session=str(d.relative_to(R)),session_status=load(d/'session-status.json'),expected_processes=len(schedule))
    save(R/'analysis/summary.json',result)
    fields=['index','block','backend','pp','tg','status','prefill_tps','decode_tps','prefill_ms_derived','decode_ms_derived','max_rss_kib','process_wall_seconds_device','voluntary_context_switches','involuntary_context_switches','directory','before_skin_c','after_skin_c','before_battery_c','after_battery_c','before_cpu_max_c','after_cpu_max_c']
    with (R/'analysis/samples.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for s in samples:
            row={k:s.get(k) for k in fields}
            for side in ['before','after']:
                for k in ['skin_c','battery_c','cpu_max_c']:row[side+'_'+k]=s.get(side,{}).get(k)
            writer.writerow(row)
    with (R/'analysis/paired-ratios.csv').open('w',newline='',encoding='utf-8') as f:
        if result['pairs']:
            writer=csv.DictWriter(f,fieldnames=result['pairs'][0]);writer.writeheader();writer.writerows(result['pairs'])
    lines=['|输入+生成|后端|n|Prefill TPS 中位数 [min,max]|Decode TPS 中位数 [min,max]|Prefill/Decode CV%|Max RSS MiB 中位数|','|---|---|---:|---|---|---|---:|']
    for g in result['groups']:
        if not g['n']:continue
        m=g['metrics'];p=m['prefill_tps'];t=m['decode_tps'];rss=m['max_rss_kib']['median']/1024
        lines.append(f'|{g["pp"]}+{g["tg"]}|{g["backend"]}|{g["n"]}|{p["median"]:.2f} [{p["min"]:.2f},{p["max"]:.2f}]|{t["median"]:.2f} [{t["min"]:.2f},{t["max"]:.2f}]|{p["cv_pct"]:.2f}/{t["cv_pct"]:.2f}|{rss:.1f}|')
    (R/'analysis/comparison-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'attempted':result['attempted'],'success':result['successful'],'failed':len(result['failed'])}));print('\n'.join(lines))
if __name__=='__main__':main()
