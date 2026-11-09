from pathlib import Path
import argparse,csv,hashlib,json,random,re,shlex,shutil,subprocess,sys,time,uuid
from adb_utils import Runner,load,save,utc,parse_benchmark
R=Path(__file__).resolve().parents[1];C=load(R.parent/'mobile-llm-runtime-lab/configs/cpu.json')
C.update(scope='Gate 2-B decode hotspot attribution',remote_root='/data/local/tmp/mnn-gate2b-20261108')
REMOTE=C['remote_root'];MODEL='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN';CONFIG=MODEL+'/config.cpu.json'
def must(rec):
    if rec['exit_code']:raise RuntimeError('Failed command: '+str(rec))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def parse_profile(raw):
    rows=[]
    for line in raw.decode('utf-8',errors='replace').splitlines():
        if not line.startswith('PROF\t') or line.startswith('PROF\tphase'):continue
        c=line.split('\t');assert len(c)==8,c
        rows.append(dict(phase=c[1],type=c[2],name=c[3],inputs=c[4],outputs=c[5],calls=int(c[6]),total_us=float(c[7])))
    assert rows,'Missing PROF rows'
    for phase in ['prefill','decode']:
        names=[r for r in rows if r['phase']==phase and r['name']!='*'];totals=[r for r in rows if r['phase']==phase and r['name']=='*']
        assert names and totals
        for t in totals:
            rr=[r for r in names if r['type']==t['type']]
            assert sum(r['calls'] for r in rr)==t['calls']
            assert abs(sum(r['total_us'] for r in rr)-t['total_us'])<max(1,len(rr)*.002)
    return rows
def device_check(r,d):
    out,_,rec=r.adb('device',['get-state'],d);must(rec)
    assert out.strip()==b'device'
    paths={REMOTE+'/'+n:(R/'staging/op_probe' if n=='op_probe' else R.parent/'gate0/staging'/n) for n in ['op_probe','llm_bench','libMNN.so']}
    for n in ['llm.mnn','llm.mnn.weight','config.cpu.json','llm_config.json','tokenizer.txt']:paths[MODEL+'/'+n]=R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n
    raw,_,rec=r.shell('hashes','sha256sum '+' '.join(paths),d);must(rec)
    got={line.split()[1]:line.split()[0] for line in raw.decode().splitlines()};expected={p:sha(f) for p,f in paths.items()}
    assert got==expected,'Assets mismatch';save(d/'verified-assets.json',expected)
def setup(r,d):
    out,_,rec=r.adb('device',['get-state'],d);must(rec);assert out.strip()==b'device'
    must(r.shell('mkdir',f'mkdir -p {REMOTE}/runs',d)[2])
    for n,local in [('llm_bench',R.parent/'gate0/staging/llm_bench'),('libMNN.so',R.parent/'gate0/staging/libMNN.so'),('op_probe',R/'staging/op_probe'),('monitor.sh',R/'scripts/monitor.sh')]:
        must(r.adb('push-'+n,['push',str(local),REMOTE+'/'+n],d)[2])
    must(r.shell('chmod',f'chmod 755 {REMOTE}/llm_bench {REMOTE}/op_probe',d)[2]);device_check(r,d)
    r.shell('metadata','getprop ro.build.fingerprint; getprop ro.soc.model; getprop ro.product.cpu.abilist; uname -a; id; getconf PAGESIZE; which simpleperf; getprop security.perf_harden',d)
    r.shell('help',f'cd {REMOTE} && LD_LIBRARY_PATH=. ./llm_bench --help',d)
def get_probe(r,d,prefix,profile):
    for suffix in ['tokens.txt','text.txt','config.json','summary.txt']+(['ops.tsv','calls.csv'] if profile else []):
        must(r.adb('pull-'+suffix,['pull',prefix+'.'+suffix,str(d/suffix)],d)[2])
    summary={k:int(v) for k,v in (line.split('=') for line in (d/'summary.txt').read_text().splitlines())}
    assert summary['status']==2 and summary['dropped']==summary['nested']==summary['foreign']==0,summary
    if profile:
        rows=list(csv.DictReader((d/'calls.csv').open()));meta={int(x['id']):x for x in csv.DictReader((d/'ops.tsv').open(),delimiter='\t')}
        assert len(rows)==summary['records']
        assert sum(meta[int(x['op'])]['type']=='Attention' and int(x['token'])>0 for x in rows)==28*summary['generated']
        assert all(int(x['ns'])>=0 for x in rows),'Negative monotonic duration'
        assert all(int(a['start_ns'])+int(a['ns'])<=int(b['start_ns']) for a,b in zip(rows,rows[1:]))
    return summary
def correctness(r,d):
    result={}
    for kind in ['synthetic','natural']:
        got={}
        for mode in ['off','detail']:
            p=d/(kind+'-'+mode);p.mkdir();r.cool(p,8);r.state('before',p)
            prefix=REMOTE+'/runs/'+d.name+'-'+p.name
            cmd=f'cd {REMOTE} && LD_LIBRARY_PATH=. /system/bin/time -v ./op_probe {CONFIG} {kind} 256 {mode} {prefix} 1'
            _,_,rec=r.shell('function',cmd,p,180);r.state('after',p)
            sm=get_probe(r,p,prefix,mode=='detail');must(rec);assert sm['generated']==256
            got[mode]={n:(p/n).read_bytes() for n in ['tokens.txt','text.txt']}
            got[mode]['meta']={k:sm[k] for k in ['status','prompt','generated','kv']}
        assert got['off']==got['detail'],'Correctness mismatch'
        result[kind]={'equal_tokens_text_and_final_state':True,'tokens_sha256':hashlib.sha256(got['off']['tokens.txt']).hexdigest(),'state':got['off']['meta']}
    save(d/'correctness-summary.json',result);print(json.dumps(result),flush=True)
def sample(r,d,i,block,mode,tg,tool):
    p=d/f'{i:03}-b{block:02}-{mode}-tg{tg}';p.mkdir();prefix=REMOTE+'/runs/'+d.name+'-'+p.name
    s={'index':i,'block':block,'mode':mode,'tg':tg,'pp':128,'tool':tool,'status':'started','started_at_utc':utc()};save(p/'sample.json',s)
    try:
        s['cooldown']=r.cool(p,12);s['before']=r.state('before',p)
        if tool=='official':
            args=['./llm_bench','-m',CONFIG,'-a','cpu','-t','4','-p','0','-n','0','-pg',f'128,{tg}','-rep','1','-c','2','--memory','2','--power','0','-dyo','0','-mmp','0','-qa','0','-fa','1','-load','false','-j',prefix+'.json']
            if mode=='profile':args.append('--profile')
        else:args=['./op_probe',CONFIG,'synthetic',str(tg),mode,prefix,'0']
        command=f'cd {REMOTE} && ( LD_LIBRARY_PATH=. MNN_LLM_BENCH_PROFILE_NAME=1 /system/bin/time -v {shlex.join(args)} & job=$!; sh ./monitor.sh "$job" > {prefix}.device.txt 2>&1 & observer=$!; wait "$job"; rc=$?; kill "$observer" 2>/dev/null; wait "$observer" 2>/dev/null; exit "$rc" )'
        out,err,rec=r.shell('run',command,p,180);s['exit_code']=rec['exit_code'];must(rec)
        s['after']=r.state('after',p)
        must(r.adb('pull-device',['pull',prefix+'.device.txt',str(p/'device-timeline.txt')],p)[2])
        if tool=='official':
            must(r.adb('pull-json',['pull',prefix+'.json',str(p/'benchmark.json')],p)[2])
            s.update(parse_benchmark(load(p/'benchmark.json'),128,tg,C))
            assert b'Incomplete sample' not in out+err
            if mode=='profile':
                rows=parse_profile(out);save(p/'profile.json',rows)
                assert next(x for x in rows if x['phase']=='decode' and x['type']=='Attention' and x['name']=='*')['calls']==28*tg
        else:
            sm=get_probe(r,p,prefix,mode=='detail');assert sm['prompt']==128 and sm['generated']==tg
            s['probe_summary']=sm;s['decode_tps']=tg*1e6/sm['decode_us'];s['prefill_tps']=128*1e6/sm['prefill_us'];s['decode_ms_derived']=sm['decode_us']/1000
        s['status']='success'
    except Exception as e:s.update(status='failed',error=str(e))
    finally:s['ended_at_utc']=utc();save(p/'sample.json',s)
    print(f'{p.name}: {s["status"]}, decode={s.get("decode_tps")}, skin={s.get("after",{}).get("skin_c")}',flush=True)
    assert s['status']=='success',s.get('error')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['setup','correctness','pilot','official','detail']);a=ap.parse_args()
    d=R/'results'/(a.phase+'-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True,exist_ok=False)
    r=Runner(C,d);save(d/'protocol.json',dict(C,phase=a.phase,config=CONFIG,started_at_utc=utc(),seed=20261110 if a.phase!='detail' else 20261111));shutil.copyfile(__file__,d/'runner-version.py')
    status={'status':'running','started_at_utc':utc()}
    try:
        if a.phase=='setup':setup(r,d)
        else:
            device_check(r,d)
            if a.phase=='correctness':correctness(r,d)
            else:
                assert list((R/'results').glob('correctness-*/correctness-summary.json'))
                tool='detail' if a.phase=='detail' else 'official';modes=['off','detail'] if tool=='detail' else ['off','profile'];blocks=2 if tool=='detail' else 6
                if a.phase=='pilot':modes=['profile'];blocks=1
                schedule=[];rng=random.Random(20261111 if tool=='detail' else 20261110)
                for b in range(1,blocks+1):
                    combos=[(m,t) for m in modes for t in [64,256]];rng.shuffle(combos);schedule.extend(dict(block=b,mode=m,tg=t,tool=tool) for m,t in combos)
                save(d/'schedule.json',schedule)
                for i,x in enumerate(schedule,1):sample(r,d,i,**x)
        status['status']='completed'
    except Exception as e:status.update(status='failed',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
