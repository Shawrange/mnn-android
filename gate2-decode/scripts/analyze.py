from pathlib import Path
import csv,hashlib,json,re,statistics as st
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def desc(x):
    x=list(x)
    return dict(n=len(x),mean=st.mean(x),median=st.median(x),min=min(x),max=max(x),sd=st.stdev(x) if len(x)>1 else None) if x else {'n':0}
def csvout(p,rows):
    if not rows:return
    with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def timeline(p):
    raw=p.read_text();ticks=[]
    for chunk in raw.split('@@TICK ')[1:]:
        t={'uptime':float(chunk.split()[0]),'policies':{},'tasks':{}}
        for pol,cur,cap in re.findall(r'(policy\d+) (\d+)\s+(\d+)',chunk):t['policies'][pol]={'cur':int(cur),'max':int(cap)}
        for tid,run,wait,slices,vol,inv in re.findall(r'@@TASK (\d+)\s+(\d+) (\d+) (\d+)\s+voluntary_ctxt_switches:\s*(\d+)\s+nonvoluntary_ctxt_switches:\s*(\d+)',chunk):
            t['tasks'][tid]={'cpu_ns':int(run),'wait_ns':int(wait),'slices':int(slices),'vol':int(vol),'invol':int(inv)}
        ticks.append(t)
    return ticks
def state_summary(samples):
    points=[x[k] for x in samples for k in ['before','after']]
    return {**{k:desc(p[k] for p in points if p.get(k) is not None) for k in ['skin_c','battery_c','cpu_max_c','mem_available_kib']},'thermal_status':sorted(set(p['thermal_status'] for p in points)),'screen_states':sorted(set(str(p['screen_state']) for p in points)),'usb_powered':sorted(set(p['usb_powered'] for p in points)), 'policy_max_khz':{pol:sorted(set(int(p['policies'][pol]['scaling_max_freq']) for p in points)) for pol in ['policy0','policy6']}}
def main():
    sessions=sorted((ROOT/'results').glob('control-*'))
    out=ROOT/'analysis';out.mkdir(exist_ok=True)
    allsamples=[];failed=[];rows=[];segments=[];events=[];trace_checks=[];state_rows=[];pairs=[];same_prefix=[];growths=[];all_steps=[]
    for session in sessions:
        data=[]
        for path in sorted(session.glob('*/sample.json')):
            s=load(path);s['path']=str(path.parent.relative_to(ROOT));s['session']=session.name
            if s['status']!='success':
                if s['status']=='failed':failed.append(s)
                continue
            data.append(s);allsamples.append(s)
            stdout=(path.parent/'benchmark.stdout.txt').read_text(errors='replace');stderr=(path.parent/'benchmark.stderr.txt').read_text(errors='replace')
            wall=re.search(r'decode wall speed \(incl. sampling\):\s*([\d.]+)',stdout)
            switches={key:int(v) for key,v in re.findall(r'(Voluntary context switches|Involuntary context switches):\s*(\d+)',stderr)}
            row={k:s[k] for k in ['session','path','index','block','mode','pp','tg','prefill_tps','decode_tps','decode_ms_derived','effective_dynamic_option']}
            row.update(wall_proxy_tps=float(wall.group(1)) if wall else None,**switches);rows.append(row)
            for key,pattern in [('max_rss_kib',r'Max RSS \(KiB\):\s*(\d+)'),('process_real_s',r'Real time \(s\):\s*([\d.]+)')]:
                match=re.search(pattern,stderr);row[key]=float(match.group(1)) if match else None
            ticks=timeline(path.parent/'device-timeline.txt');save(out/'timelines'/(path.parent.name+'.json'),ticks)
            state_rows.append({'path':s['path'],'ticks':len(ticks),'policy_cur':{pol:desc(t['policies'][pol]['cur'] for t in ticks if pol in t['policies']) for pol in ['policy0','policy6']},'policy_max':{pol:sorted(set(t['policies'][pol]['max'] for t in ticks if pol in t['policies'])) for pol in ['policy0','policy6']},'tasks_with_schedstat':max((len(t['tasks']) for t in ticks),default=0)})
            if s['mode']!='on':continue
            allrr=[{k:int(v) for k,v in r.items()} for r in csv.DictReader((path.parent/'trace.steps.csv').open())]
            response=max(r['response'] for r in allrr);rr=[r for r in allrr if r['response']==response]
            all_steps.extend(dict(path=s['path'],tg=s['tg'],**r) for r in rr)
            total=sum(r['wall_ns'] for r in rr)/1e6
            assert len(rr)==s['tg'] and all(r['attention_count']==28 and r['kv_count']==28 for r in rr)
            trace_checks.append({'path':s['path'],'native_decode_ms':s['decode_ms_derived'],'trace_step_sum_ms':total,'trace_minus_native_ms':total-s['decode_ms_derived'],'response':response,'steps':len(rr),'first_kv':rr[0]['kv_before'],'last_kv':rr[-1]['kv_after']})
            for begin in range(0,s['tg'],64):
                chunk=rr[begin:begin+64]
                d={'path':s['path'],'block':s['block'],'tg':s['tg'],'segment':begin//64+1,'token_begin':begin+1,'token_end':begin+len(chunk),'kv_before_begin':chunk[0]['kv_before'],'kv_after_end':chunk[-1]['kv_after']}
                for key in ['wall_ns','attention_ns','alloc_ns','realloc_ns','update_ns','caller_cpu_ns']:
                    d[key.replace('_ns','_ms_mean')]=st.mean(r[key] for r in chunk)/1e6
                d['non_attention_ms_mean']=d['wall_ms_mean']-d['attention_ms_mean'];d['attention_share']=sum(r['attention_ns'] for r in chunk)/sum(r['wall_ns'] for r in chunk)
                d['attention_minus_kv_ms_mean']=d['attention_ms_mean']-d['alloc_ms_mean']-d['realloc_ms_mean']-d['update_ms_mean']
                steady=[r for r in chunk if r['token'] not in [65,130,195]]
                d['wall_without_growth_steps_ms_mean']=st.mean(r['wall_ns'] for r in steady)/1e6
                d['attention_without_growth_steps_ms_mean']=st.mean(r['attention_ns'] for r in steady)/1e6
                segments.append(d)
            ge=[{k:int(v) for k,v in r.items()} for r in csv.DictReader((path.parent/'trace.growth.csv').open()) if int(r['response'])==response]
            for r in ge:events.append(dict(path=s['path'],**r))
            for token in sorted(set(r['token'] for r in ge)):
                e=[r for r in ge if r['token']==token];t=rr[token-1]
                neighbors=[r for r in rr[max(0,token-4):min(len(rr),token+3)] if r['token']!=token]
                growths.append({'path':s['path'],'token':token,'managers':len(e),'capacity_before':e[0]['capacity_before'],'capacity_after':e[0]['capacity_after'],'in_disk':sorted(set(x['in_disk'] for x in e)),'wall_ms':t['wall_ns']/1e6,'realloc_ms':t['realloc_ns']/1e6,'nearby_median_wall_ms':st.median(r['wall_ns'] for r in neighbors)/1e6,'realloc_share_of_whole_decode':t['realloc_ns']/sum(r['wall_ns'] for r in rr)})
        for b in sorted(set(s['block'] for s in data)):
            for mode in ['clean','off','on']:
                dd={s['tg']:s for s in data if s['block']==b and s['mode']==mode}
                if len(dd)==2:pairs.append({'session':session.name,'block':b,'kind':'length','mode':mode,'percent':100*(dd[256]['decode_tps']/dd[64]['decode_tps']-1)})
            for tg in [64,256]:
                dd={s['mode']:s for s in data if s['block']==b and s['tg']==tg}
                for a,z in [('off','on'),('clean','off')]:
                    if a in dd and z in dd:
                        pairs.append({'session':session.name,'block':b,'kind':a+'-to-'+z,'mode':str(tg),'percent':100*(dd[a]['decode_tps']/dd[z]['decode_tps']-1)})
            on=[s for s in data if s['block']==b and s['mode']=='on']
            if len(on)==2:
                traces=[]
                for s in sorted(on,key=lambda s:s['tg']):
                    rr=list(csv.DictReader((ROOT/s['path']/'trace.steps.csv').open()));last=max(int(r['response']) for r in rr);traces.append([int(r['token_id']) for r in rr if int(r['response'])==last])
                same_prefix.append({'block':b,'equal_first64':traces[0]==traces[1][:64]})
    summary={'sessions':[str(s.relative_to(ROOT)) for s in sessions],'samples':len(allsamples),'failed':failed,'groups':{f'{mode}-{tg}':{key:desc(s[key] for s in allsamples if s['mode']==mode and s['tg']==tg) for key in ['decode_tps','prefill_tps']} for mode in ['clean','off','on'] for tg in [64,256]},'paired_summary':{kind+'-'+mode:desc(p['percent'] for p in pairs if p['kind']==kind and p['mode']==mode) for kind,mode in sorted(set((p['kind'],p['mode']) for p in pairs))},'segments':{str(segment):{key:desc(s[key] for s in segments if s['tg']==256 and s['segment']==segment) for key in ['wall_ms_mean','attention_ms_mean','non_attention_ms_mean','realloc_ms_mean','update_ms_mean','attention_share','attention_minus_kv_ms_mean','wall_without_growth_steps_ms_mean','attention_without_growth_steps_ms_mean']} for segment in range(1,5)},'growth_by_token':{str(t):{key:desc(g[key] for g in growths if g['token']==t) for key in ['wall_ms','realloc_ms','nearby_median_wall_ms','realloc_share_of_whole_decode']} for t in sorted(set(g['token'] for g in growths))},'trace_checks':trace_checks,'same_token_prefix':same_prefix,'device':state_summary(allsamples) if allsamples else {}}
    deltas=[]
    for p in sorted(set(s['path'] for s in segments if s['tg']==256)):
        ss={s['segment']:s for s in segments if s['path']==p}
        deltas.append({'path':p,**{key:ss[4][key]-ss[1][key] for key in ['wall_ms_mean','attention_ms_mean','non_attention_ms_mean','attention_minus_kv_ms_mean']}})
    summary['within_run_last_minus_first']= {key:desc(d[key] for d in deltas) for key in ['wall_ms_mean','attention_ms_mean','non_attention_ms_mean','attention_minus_kv_ms_mean']}
    summary['within_run_deltas']=deltas
    summary['largest_steps']=sorted(all_steps,key=lambda r:r['wall_ns'],reverse=True)[:10]
    save(out/'summary.json',summary);save(out/'timeline-summary.json',state_rows);save(out/'growth-summary.json',growths)
    for name,data in [('samples',rows),('segments',segments),('growth-events',events),('paired',pairs)]:csvout(out/(name+'.csv'),data)
    print(json.dumps({k:summary[k] for k in ['samples','groups','paired_summary','segments']},indent=2))
if __name__=='__main__':main()
