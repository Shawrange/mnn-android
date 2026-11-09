from pathlib import Path
import argparse,csv,hashlib,json,random,shlex,shutil,sys,subprocess,time,uuid
from gate1_runner import Runner,load,save,utc,parse_benchmark
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'mobile-llm-runtime-lab'
C=load(BASE/'configs/cpu.json')
C['scope']='Gate 2-A decode mechanism study; isolated from Gate 1'
REMOTE=C['remote_root']+'/gate2a-diagnostic'
CONFIG=C['remote_root']+'/'+C['remote_config']

def must(rec):
    if rec['exit_code']:raise RuntimeError('Command failed: '+str(rec))

def validate_trace(d,tg):
    rows=list(csv.DictReader((d/'trace.steps.csv').open()))
    status=dict(line.split('=') for line in (d/'trace.status.txt').read_text().splitlines())
    assert int(status['dropped'])==0,status
    responses=sorted(set(int(r['response']) for r in rows))
    assert len(responses)==2,(responses,len(rows))
    for response in responses:
        rr=[r for r in rows if int(r['response'])==response]
        assert len(rr)==tg,(response,len(rr),tg)
        for i,r in enumerate(rr,1):
            assert int(r['token'])==i and int(r['kv_before'])==127+i and int(r['kv_after'])==128+i,r
            assert int(r['attention_count'])==28 and int(r['kv_count'])==28,r
            assert 0<int(r['attention_ns'])<=int(r['wall_ns']),r
    return {'status':status,'responses':responses,'tokens_per_response':tg,'attention_per_token':28,'kv_updates_per_token':28}

def setup(r,d):
    must(r.shell('mkdir',f'mkdir -p {REMOTE}/clean {REMOTE}/diag {REMOTE}/runs',d)[2])
    for mode,local in [('clean',ROOT.parent/'gate0/staging'),('diag',ROOT/'staging')]:
        for n in ['libMNN.so','llm_bench']:
            must(r.adb('push-'+mode+'-'+n,['push',str(local/n),REMOTE+'/'+mode+'/'+n],d)[2])
    for name,local in [('correctness',ROOT/'staging/correctness'),('monitor.sh',ROOT/'scripts/monitor.sh')]:
        must(r.adb('push-'+name,['push',str(local),REMOTE+'/'+name],d)[2])
    must(r.shell('chmod',f'chmod 755 {REMOTE}/clean/llm_bench {REMOTE}/diag/llm_bench {REMOTE}/correctness',d)[2])
    paths=[f'{m}/{n}' for m in ['clean','diag'] for n in ['libMNN.so','llm_bench']]+['correctness','monitor.sh']
    raw,_,rec=r.shell('hashes','cd '+REMOTE+' && sha256sum '+' '.join(paths),d);must(rec)
    got={line.split()[1]:line.split()[0] for line in raw.decode().splitlines()}
    for name in paths:
        if name.startswith('clean/'):local=ROOT.parent/'gate0/staging'/name.split('/')[1]
        elif name.startswith('diag/'):local=ROOT/'staging'/name.split('/')[1]
        else:local=ROOT/('scripts' if name.endswith('.sh') else 'staging')/name
        assert got[name]==hashlib.sha256(local.read_bytes()).hexdigest()
    save(d/'verified-assets.json',got)
    r.shell('device','getprop ro.build.fingerprint; getprop ro.soc.model; uname -a; id; getconf PAGESIZE',d)
    r.shell('permissions','cat /sys/class/thermal/thermal_zone0/temp; cat /proc/self/schedstat; ls /data/local/tmp',d)
    for f in ['model-lock.json','config.cpu.json','llm_config.json']:
        source=next((BASE/'results/baseline-20261108T140723-9efc5f25').glob(f));shutil.copyfile(source,d/f)

def correctness(r,d):
    comparisons={}
    for kind in ['synthetic','natural']:
        outputs={}
        for mode in ['clean','off','on']:
            p=d/(kind+'-'+mode);p.mkdir();remote=REMOTE+'/runs/'+d.name+'-'+p.name
            r.cool(p,8);r.state('before',p)
            env=f'LD_LIBRARY_PATH={REMOTE}/'+('clean' if mode=='clean' else 'diag')
            if mode=='on':env+=' MNN_GATE2_TRACE_PREFIX='+remote+'.trace'
            cmd=f'cd {REMOTE} && {env} /system/bin/time -v ./correctness {CONFIG} {kind} {remote}'
            _,_,rec=r.shell('correctness',cmd,p,180);must(rec);r.state('after',p)
            for suffix in ['tokens.txt','text.txt','meta.txt']:
                must(r.adb('pull-'+suffix,['pull',remote+'.'+suffix,str(p/suffix)],p)[2])
            if mode=='on':
                for suffix in ['steps.csv','growth.csv','status.txt']:
                    must(r.adb('pull-'+suffix,['pull',remote+'.trace.'+suffix,str(p/('trace.'+suffix))],p)[2])
            outputs[mode]={suffix:(p/suffix).read_bytes() for suffix in ['tokens.txt','text.txt','meta.txt']}
        assert outputs['clean']==outputs['off']==outputs['on'],'Correctness mismatch: '+kind
        comparisons[kind]={'matched_modes':['clean','off','on'],'generated_tokens':len(outputs['clean']['tokens.txt'].splitlines()),'tokens_sha256':hashlib.sha256(outputs['clean']['tokens.txt']).hexdigest(),'meta':outputs['clean']['meta.txt'].decode(),'text_sha256':hashlib.sha256(outputs['clean']['text.txt']).hexdigest()}
    save(d/'correctness-summary.json',comparisons)
    print(json.dumps(comparisons,ensure_ascii=False),flush=True)

def sample(r,d,index,block,mode,tg):
    p=d/f'{index:03}-b{block:02}-{mode}-tg{tg}';p.mkdir()
    s={'index':index,'block':block,'mode':mode,'tg':tg,'pp':128,'status':'started','started_at_utc':utc()}
    save(p/'sample.json',s)
    try:
        s['cooldown']=r.cool(p,12);s['before']=r.state('before',p)
        remote=REMOTE+'/runs/'+d.name+'-'+p.name
        binary=REMOTE+'/'+('clean' if mode=='clean' else 'diag')+'/llm_bench'
        args=[binary,'-m',CONFIG,'-a','cpu','-t','4','-p','0','-n','0','-pg',f'128,{tg}','-rep','1','-c','2','--memory','2','--power','0','-dyo','0','-mmp','0','-qa','0','-fa','1','-load','false','-j',remote+'.json']
        env='LD_LIBRARY_PATH='+REMOTE+'/'+('clean' if mode=='clean' else 'diag')
        if mode=='on':env+=' MNN_GATE2_TRACE_PREFIX='+remote+'.trace'
        cmd=f'cd {REMOTE} && ( {env} /system/bin/time -v {shlex.join(args)} & job=$!; sh ./monitor.sh "$job" > {remote}.device.txt 2>&1 & observer=$!; wait "$job"; rc=$?; kill "$observer" 2>/dev/null; wait "$observer" 2>/dev/null; exit "$rc" )'
        out,err,rec=r.shell('benchmark',cmd,p,180);s['exit_code']=rec['exit_code'];must(rec)
        s['after']=r.state('after',p)
        for remote_suffix,local in [('.json','benchmark.json'),('.device.txt','device-timeline.txt')]:
            must(r.adb('pull-'+local,['pull',remote+remote_suffix,str(p/local)],p)[2])
        if b'Incomplete sample' in out+err or b'INTERNAL_ERROR' in out+err:raise RuntimeError('Native invalid sample')
        s.update(parse_benchmark(load(p/'benchmark.json'),128,tg,C))
        if mode=='on':
            for suffix in ['steps.csv','growth.csv','status.txt']:
                must(r.adb('pull-'+suffix,['pull',remote+'.trace.'+suffix,str(p/('trace.'+suffix))],p)[2])
            s['trace_validation']=validate_trace(p,tg)
        s['status']='success'
    except Exception as e:
        s['status']='failed';s['error']=str(e)
    finally:
        s['ended_at_utc']=utc();save(p/'sample.json',s)
    print(f'{p.name}: {s["status"]}, decode={s.get("decode_tps")}, skin={s.get("after",{}).get("skin_c")}',flush=True)
    if s['status']!='success':raise RuntimeError('Sample failed: '+str(s.get('error')))
    return s

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['setup','correctness','pilot','control']);ap.add_argument('--blocks',type=int,default=6);a=ap.parse_args()
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]
    d=ROOT/'results'/(a.phase+'-'+stamp);d.mkdir(parents=True,exist_ok=False)
    r=Runner(C,d);save(d/'protocol.json',dict(C,phase=a.phase,blocks=a.blocks,remote=REMOTE,config=CONFIG,monotonic_trace=True,observer_interval_s=0.5,start=utc()))
    shutil.copyfile(__file__,d/'runner-version.py');status={'status':'running'}
    try:
        if a.phase=='setup':setup(r,d)
        elif a.phase=='correctness':correctness(r,d)
        else:
            if a.phase=='control':assert list((ROOT/'results').glob('correctness-*/correctness-summary.json')),'Correctness required'
            schedule=[];rng=random.Random(20261109)
            for b in range(1,(1 if a.phase=='pilot' else a.blocks)+1):
                combos=[(m,tg) for m in (['on'] if a.phase=='pilot' else ['clean','off','on']) for tg in [64,256]];rng.shuffle(combos)
                schedule += [{'block':b,'mode':m,'tg':tg} for m,tg in combos]
            save(d/'schedule.json',schedule)
            for i,x in enumerate(schedule,1):sample(r,d,i,**x)
        status['status']='completed'
    except Exception as e:status.update(status='failed',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(str(d),flush=True)
if __name__=='__main__':main()
