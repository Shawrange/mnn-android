from pathlib import Path
import csv,json,statistics as st,re,collections,math
R=Path(__file__).resolve().parents[1];A=R/'analysis';A.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def quant(x,q):
    x=sorted(x);i=(len(x)-1)*q;lo=int(i);hi=min(lo+1,len(x)-1);return x[lo]+(x[hi]-x[lo])*(i-lo)
def desc(x):
    x=list(x)
    return dict(n=len(x),mean=st.mean(x),median=st.median(x),min=min(x),max=max(x),q25=quant(x,.25),q75=quant(x,.75),sd=st.stdev(x) if len(x)>1 else None) if x else {'n':0}
def outcsv(name,rows):
    if not rows:return
    with (A/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
def category(typ,name):
    if typ=='Convolution':
        if '/mlp/' in name:return 'MLP linear'
        if '/lm_head/' in name:return 'Vocabulary head linear'
        if '/self_attn/' in name:return 'QKV/O linear'
        return 'Other convolution'
    return {'LayerNorm':'Norm','Raster':'Layout/Raster','While':'Geometry While','BinaryOp':'Elementwise binary','UnaryOp':'Elementwise unary','Cast':'Cast','Attention':'Attention'}.get(typ,typ)
def main():
    samples=[];failed=[];oprows=[];catrows=[];residuals=[];detailrows=[];detailruns=[];detailsegments=[];device=[];node_distributions=[]
    for phase in ['official','detail']:
        for session in sorted((R/'results').glob(phase+'-*')):
            for p in sorted(session.glob('*/sample.json')):
                s=load(p);s['session']=session.name;s['path']=str(p.parent.relative_to(R))
                if s['status']!='success':
                    if s['status']=='failed':failed.append(s)
                    continue
                stdout=(p.parent/'run.stdout.txt').read_text(errors='replace');stderr=(p.parent/'run.stderr.txt').read_text(errors='replace')
                m=re.search(r'decode wall speed \(incl. sampling\):\s*([\d.]+)',stdout)
                s['wall_proxy_tps']=float(m.group(1)) if m else (s['tg']*1e9/(s['probe_summary']['response_wall_ns']-s['probe_summary']['prefill_us']*1000) if s['tool']=='detail' else None)
                for key,pat in [('rss_kib',r'Max RSS \(KiB\):\s*(\d+)'),('real_s',r'Real time \(s\):\s*([\d.]+)'),('involuntary',r'Involuntary context switches:\s*(\d+)')]:
                    m=re.search(pat,stderr);s[key]=float(m.group(1)) if m else None
                samples.append(s)
                raw=(p.parent/'device-timeline.txt').read_text()
                ticks=[]
                for chunk in raw.split('@@CLOCK ')[1:]:
                    first=chunk.splitlines()[0].split()
                    if len(first)!=2 or not all(i.isdigit() for i in first):continue
                    t={'mono_ns':int(first[0]),'boot_ns':int(first[1]),'policies':{}}
                    for pol,cur,cap in re.findall(r'(policy\d+) (\d+)\s+(\d+)',chunk):t['policies'][pol]={'cur':int(cur),'cap':int(cap)}
                    ticks.append(t)
                device.append({'path':s['path'],'ticks':len(ticks),'clock_offset_ns':desc(t['boot_ns']-t['mono_ns'] for t in ticks),'policies':{pol:{key:desc(t['policies'][pol][key] for t in ticks if pol in t['policies']) for key in ['cur','cap']} for pol in ['policy0','policy6']}})
                if phase=='official' and s['mode']=='profile':
                    prof=load(p.parent/'profile.json');named=[x for x in prof if x['phase']=='decode' and x['name']!='*'];typed=[x for x in prof if x['phase']=='decode' and x['name']=='*'];total=sum(x['total_us'] for x in typed)
                    assert abs(sum(x['total_us'] for x in named)-total)<3
                    cat=collections.defaultdict(lambda:{'us':0,'calls':0})
                    for x in named:
                        c=category(x['type'],x['name']);cat[c]['us']+=x['total_us'];cat[c]['calls']+=x['calls']
                        oprows.append({'path':s['path'],'tg':s['tg'],'type':x['type'],'name':x['name'],'category':c,'calls':x['calls'],'calls_per_token':x['calls']/s['tg'],'total_us':x['total_us'],'us_per_call':x['total_us']/x['calls'],'ms_per_token':x['total_us']/s['tg']/1000,'share_op_percent':100*x['total_us']/total,'inputs':x['inputs'],'outputs':x['outputs']})
                    for c,v in cat.items():catrows.append({'path':s['path'],'tg':s['tg'],'category':c,'calls_per_token':v['calls']/s['tg'],'ms_per_token':v['us']/s['tg']/1000,'share_op_percent':100*v['us']/total,'share_native_percent':100*v['us']/(s['decode_ms_derived']*1000)})
                    residuals.append({'path':s['path'],'tg':s['tg'],'native_ms':s['decode_ms_derived'],'op_ms':total/1000,'residual_ms':s['decode_ms_derived']-total/1000,'residual_per_token_ms':(s['decode_ms_derived']-total/1000)/s['tg'],'coverage_percent':100*total/(s['decode_ms_derived']*1000),'calls_per_token':sum(x['calls'] for x in typed)/s['tg']})
                if phase=='detail' and s['mode']=='detail':
                    meta={int(x['id']):x for x in csv.DictReader((p.parent/'ops.tsv').open(),delimiter='\t')}
                    bytype=collections.defaultdict(list);bycat=collections.defaultdict(list);bynode=collections.defaultdict(list);bytoken=collections.defaultdict(lambda:collections.defaultdict(int));allcalls=[];zero=0
                    for x in csv.DictReader((p.parent/'calls.csv').open()):
                        if int(x['token'])<=0:continue
                        m=meta[int(x['op'])];us=int(x['ns'])/1000;c=category(m['type'],m['name']);t=int(x['token']);zero+=us==0
                        bytype[m['type']].append(us);bycat[c].append(us);bynode[(m['type'],m['name'])].append(us);bytoken[t][c]+=int(x['ns']);allcalls.append((int(x['start_ns']),int(x['ns'])))
                    for typ,v in bytype.items():detailrows.append({'path':s['path'],'tg':s['tg'],'type':typ,'calls':len(v),'calls_per_token':len(v)/s['tg'],'mean_us':st.mean(v),'median_us':st.median(v),'p95_us_descriptive':quant(v,.95),'min_us':min(v),'max_us':max(v),'sum_ms':sum(v)/1000})
                    for (typ,name),v in bynode.items():node_distributions.append({'path':s['path'],'tg':s['tg'],'type':typ,'name':name,'calls':len(v),'mean_us':st.mean(v),'median_us':st.median(v),'p95_us_descriptive':quant(v,.95),'min_us':min(v),'max_us':max(v),'sum_ms':sum(v)/1000})
                    for begin in range(1,s['tg']+1,64):
                        catset=sorted(bycat)
                        for c in catset:detailsegments.append({'path':s['path'],'tg':s['tg'],'segment':(begin-1)//64+1,'category':c,'ms_per_token':st.mean(bytoken[t][c] for t in range(begin,begin+64))/1e6})
                    detailruns.append({'path':s['path'],'tg':s['tg'],'zero_duration_calls':zero,'decode_calls':len(allcalls),'op_sum_ms':sum(x[1] for x in allcalls)/1e6,'native_decode_ms':s['decode_ms_derived'],'new_metadata_measured':s['probe_summary']['new_metadata_measured'],'nested':s['probe_summary']['nested'],'foreign':s['probe_summary']['foreign'],'dropped':s['probe_summary']['dropped']})
                    selected=[t for t in ticks if allcalls[0][0]<=t['mono_ns']<=allcalls[-1][0]+allcalls[-1][1]]
                    device[-1]['decode_window_ticks']=len(selected)
                    device[-1]['decode_policy_cur_khz']={pol:desc(t['policies'][pol]['cur'] for t in selected if pol in t['policies']) for pol in ['policy0','policy6']}
    outcsv('samples.csv',[{k:s.get(k) for k in ['session','path','block','tool','mode','pp','tg','decode_tps','prefill_tps','decode_ms_derived','wall_proxy_tps','rss_kib','real_s','involuntary']} for s in samples]);outcsv('named-ops.csv',oprows);outcsv('categories.csv',catrows);outcsv('residuals.csv',residuals);outcsv('detail-call-distributions.csv',detailrows);outcsv('detail-segments.csv',detailsegments)
    overhead=[]
    for session in sorted(set(s['session'] for s in samples)):
        ss=[s for s in samples if s['session']==session];mode='profile' if session.startswith('official') else 'detail'
        for b in sorted(set(s['block'] for s in ss)):
            for tg in [64,256]:
                dd={s['mode']:s for s in ss if s['block']==b and s['tg']==tg}
                if len(dd)<2:continue
                overhead.append({'session':session,'block':b,'tg':tg,'mode':mode,'native_time_change_percent':100*(dd['off']['decode_tps']/dd[mode]['decode_tps']-1),'wall_proxy_change_percent':100*(dd['off']['wall_proxy_tps']/dd[mode]['wall_proxy_tps']-1)})
    outcsv('overhead-pairs.csv',overhead)
    outcsv('detail-node-distributions.csv',node_distributions)
    summary={'successful':len(samples),'failed_samples':failed,'groups':{tool+'-'+mode+'-'+str(tg):{key:desc(s[key] for s in samples if s['tool']==tool and s['mode']==mode and s['tg']==tg) for key in ['decode_tps','prefill_tps','rss_kib','involuntary']} for tool,mode,tg in sorted(set((s['tool'],s['mode'],s['tg']) for s in samples))},'overhead':{mode+'-'+str(tg):{key:desc(s[key] for s in overhead if s['mode']==mode and s['tg']==tg) for key in ['native_time_change_percent','wall_proxy_change_percent']} for mode,tg in sorted(set((s['mode'],s['tg']) for s in overhead))},'categories':{str(tg):{c:{key:desc(r[key] for r in catrows if r['tg']==tg and r['category']==c) for key in ['calls_per_token','ms_per_token','share_op_percent','share_native_percent']} for c in sorted(set(r['category'] for r in catrows))} for tg in [64,256]},'residuals':{str(tg):{key:desc(r[key] for r in residuals if r['tg']==tg) for key in ['residual_per_token_ms','coverage_percent','calls_per_token']} for tg in [64,256]},'detail_runs':detailruns,'device_timeline':device}
    points=[s[k] for s in samples for k in ['before','after']]
    if points:summary['device']={**{k:desc(s[k] for s in points) for k in ['skin_c','battery_c','cpu_max_c','mem_available_kib']},'usb_powered':sorted(set(s['usb_powered'] for s in points)),'screen':sorted(set(str(s['screen_state']) for s in points)),'thermal_status':sorted(set(s['thermal_status'] for s in points)),'policy_caps':{pol:sorted(set(int(p['policies'][pol]['scaling_max_freq']) for p in points)) for pol in ['policy0','policy6']}}
    summary['failed_sessions']=[{'path':str(p.parent.relative_to(R)),**load(p)} for p in (R/'results').glob('*/session-status.json') if load(p)['status']=='failed']
    conv=[]
    for path in sorted(set(r['path'] for r in catrows)):
        rr=[r for r in catrows if r['path']==path and r['category'] in ['MLP linear','QKV/O linear','Vocabulary head linear']]
        conv.append({'path':path,'tg':rr[0]['tg'],**{key:sum(r[key] for r in rr) for key in ['calls_per_token','ms_per_token','share_op_percent','share_native_percent']}})
    summary['convolution_total']={str(tg):{key:desc(r[key] for r in conv if r['tg']==tg) for key in ['calls_per_token','ms_per_token','share_op_percent','share_native_percent']} for tg in [64,256]}
    save(A/'summary.json',summary);save(A/'device-timeline-summary.json',device)
    print('Successful formal/diagnostic samples:',len(samples),'Failed sessions:',len(summary['failed_sessions']))
if __name__=='__main__':main()
