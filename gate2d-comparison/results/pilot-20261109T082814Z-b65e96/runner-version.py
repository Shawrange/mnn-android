"""Bounded experiment using the archived official llm_bench, stdlib only."""
from adb_utils import Runner,load,save,utc
from pathlib import Path
import argparse,hashlib,json,math,platform,random,re,shlex,shutil,sys,time,uuid
R=Path(__file__).resolve().parents[1]
C={'adb':r'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe','serial':'ee19377b',
   'mnn_commit':'7e3c6fb5225d3ccf22807ee641332669df34650d','model_revision':'34dfccda1187ded6e07ea06426da576b0b793c6b',
   'cooling':{'max_skin_c':38.,'max_battery_c':36.,'max_current_cpu_c':80.,'max_wait_seconds':300,'poll_seconds':15}}
MODEL='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def must(rec):
    if rec['exit_code']:raise RuntimeError('Command failed: '+str(rec))
def inventory(r,label,remote,d):
    r.shell(label,f'find {remote} -type f -exec ls -ln {{}} \\; ; find {remote} -name mnn_cachefile.bin -exec sha256sum {{}} \\;',d)
def parse(data,backend,pp,tg):
    for k,v in {'backend':{'cpu':'CPU','opencl':'OPENCL'}[backend],'threads':4,'precision':2,'memory':2,'power':0,'quantKv':0,'flashAttention':1,'useMmap':False}.items():
        if data.get(k)!=v:raise ValueError(f'JSON config mismatch {k}: {data.get(k)}')
    rows=data.get('results',[])
    if len(rows)!=1:raise ValueError('Expected exactly one JSON result')
    row=rows[0]
    if (row['type'],row['prompt_len'],row['generate_len'])!=('prefill_and_decode',pp,tg):raise ValueError('Wrong workload')
    for k in ['prefill_tps','decode_tps']:
        if not math.isfinite(row[k]) or row[k]<=0:raise ValueError('Invalid TPS')
    return {'prefill_tps':row['prefill_tps'],'decode_tps':row['decode_tps'],
            'prefill_ms_derived':1000*pp/row['prefill_tps'],'decode_ms_derived':1000*tg/row['decode_tps'],
            'effective_dynamic_option':0,'cpu_threads':4 if backend=='cpu' else None,'opencl_mode_bits':580 if backend=='opencl' else None,
            'actual_length_evidence':'functional count probe + fixed source loop/ignore_eos + successful native validity checks; no per-run count exported',
            'actual_length_directly_exported':False,'request_e2e_ms':None,'ttft_ms':None,'pss_kib':None,'gpu_vram_kib':None}
def run_sample(r,d,item,remote):
    b,pp,tg=item['backend'],item['pp'],item['tg'];d.mkdir(exist_ok=False)
    s=dict(item,status='started',started_at_utc=utc());save(d/'sample.json',s)
    try:
        s['cooldown']=r.cool(d,15);s['before']=r.state('before',d)
        wd=f'{remote}/{b}';output=f'{wd}/sample-{item["index"]:03}.json'
        args=['./llm_bench','-m','config.json','-a',b,'-t','4','-p','0','-n','0','-pg',f'{pp},{tg}','-rep','1','-c','2','--memory','2','--power','0','-dyo','0','-mmp','0','-qa','0','-fa','1','-load','false','-j',output]
        cmd=f'cd {wd} && LD_LIBRARY_PATH=. /system/bin/time -v '+shlex.join(args)
        out,err,rec=r.shell('benchmark',cmd,d,600);s['exit_code']=rec['exit_code'];s['process_wall_seconds_host']=rec['elapsed_seconds']
        s['after']=r.state('after',d)
        _,_,pull=r.adb('pull-json',['pull',output,str(d/'benchmark.json')],d);s['json_pull_exit_code']=pull['exit_code']
        must(rec);must(pull)
        if re.search(rb'Incomplete sample|INTERNAL_ERROR|LLM init error|CANNOT LINK|Error:|\[Error\]|not support|Fallback',out+err,re.I):raise ValueError('Error/fallback marker in logs')
        s.update(parse(load(d/'benchmark.json'),b,pp,tg))
        e=err.decode('utf-8',errors='replace')
        for key,pattern in [('max_rss_kib',r'Max RSS \(KiB\):\s*(\d+)'),('process_wall_seconds_device',r'Real time \(s\):\s*([\d.]+)'),('major_faults',r'Major faults:\s*(\d+)'),('minor_faults',r'Minor faults:\s*(\d+)'),('voluntary_context_switches',r'Voluntary context switches:\s*(\d+)'),('involuntary_context_switches',r'Involuntary context switches:\s*(\d+)')]:
            m=re.search(pattern,e);s[key]=float(m.group(1)) if m else None
        m=re.search(rb'decode wall speed \(incl. sampling\):\s*([\d.]+)',out);s['decode_wall_tps_rounded']=float(m.group(1)) if m else None
        if s['max_rss_kib'] is None:raise ValueError('Missing process Max RSS')
        s['status']='success'
    except Exception as ex:s.update(status='failed',error=str(ex))
    s['ended_at_utc']=utc();save(d/'sample.json',s)
    print(f'{item["index"]:02} b{item["block"]} {b} {pp}+{tg} {s["status"]} pp={s.get("prefill_tps")} tg={s.get("decode_tps")} process_s={s.get("process_wall_seconds_device")} skin={s.get("after",{}).get("skin_c")}',flush=True)
    return s
def deploy():
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]
    d=R/'results'/('setup-'+stamp);d.mkdir();r=Runner(C,d);remote='/data/local/tmp/mnn-gate2d-'+stamp
    must(r.adb('device',['get-state'],d)[2]);must(r.shell('mkdir','mkdir '+remote,d)[2])
    for b in ['cpu','opencl']:
        wd=remote+'/'+b;must(r.shell('mkdir-'+b,'mkdir '+wd,d)[2])
        for n in ['libMNN.so','llm_bench']:must(r.adb(f'push-{b}-{n}',['push',str(R/'staging'/b/n),wd+'/'+n],d)[2])
        must(r.adb('config-'+b,['push',str(R/'configs'/f'{b}.json'),wd+'/config.json'],d)[2])
        must(r.shell('chmod-'+b,'chmod 755 '+wd+'/llm_bench',d)[2])
    files={f'{remote}/{b}/{n}':sha(R/'staging'/b/n) for b in ['cpu','opencl'] for n in ['libMNN.so','llm_bench']}
    files.update({f'{remote}/{b}/config.json':sha(R/'configs'/f'{b}.json') for b in ['cpu','opencl']})
    files.update({f'{MODEL}/{n}':sha(R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n) for n in ['llm.mnn','llm.mnn.weight','tokenizer.txt','llm_config.json']})
    out,_,rec=r.shell('hashes','sha256sum '+' '.join(files),d,90);must(rec)
    actual={x.split()[1]:x.split()[0] for x in out.decode().splitlines()};assert actual==files
    save(d/'verified-assets.json',files)
    r.shell('device-metadata','id; getprop ro.build.fingerprint; getprop ro.soc.model; getprop ro.build.version.release; getprop ro.build.version.sdk; uname -a; getconf PAGESIZE; getenforce',d)
    r.shell('time-capability','/system/bin/time -v sleep 0.01',d)
    r.shell('help',f'cd {remote}/cpu && LD_LIBRARY_PATH=. ./llm_bench --help',d)
    inventory(r,'initial-cache-inventory',remote,d)
    save(R/'deployment.json',{'remote':remote,'setup':str(d.relative_to(R)),'hashes':files,'created_at_utc':utc()})
    print('Deployment',remote)
def count_probe():
    dep=load(R/'deployment.json');remote=dep['remote'];d=R/'results'/('functional-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));d.mkdir();r=Runner(C,d)
    for b in ['cpu','opencl']:
        sub=d/b;sub.mkdir();wd=remote+'/'+b
        must(r.adb('push',['push',str(R/'staging/count_probe'),wd+'/count_probe'],sub)[2]);must(r.shell('chmod','chmod 755 '+wd+'/count_probe',sub)[2])
        r.cool(sub,15)
        must(r.shell('run',f'cd {wd} && LD_LIBRARY_PATH=. ./count_probe config.json {b} count-contract.json',sub,600)[2])
        must(r.adb('pull',['pull',wd+'/count-contract.json',str(sub/'count-contract.json')],sub)[2])
        v=load(sub/'count-contract.json');assert len(v['runs'])==6
        for s in v['runs']:assert len(s['input_ids'])==s['pp'] and set(s['input_ids'])=={16} and s['tg']==s['gen_seq_len']==len(s['output_ids']) and s['kv_after']==s['pp']+s['tg']
        print('Functional exact lengths and KV reset verified:',b,flush=True)
    save(d/'session-status.json',{'status':'completed','at_utc':utc()})
def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['deploy','pilot','count','formal']);a=ap.parse_args()
    if a.phase=='deploy':deploy();return
    if a.phase=='count':count_probe();return
    dep=load(R/'deployment.json');remote=dep['remote'];schedule=[]
    if a.phase=='pilot':
        for b,pp,tg in [('opencl',32,64),('opencl',128,256),('cpu',128,64)]:schedule.append(dict(block=0,backend=b,pp=pp,tg=tg))
    else:
        assert not (R/'FORMAL_STARTED.json').exists(),'Exactly one formal session permitted'
        frozen=load(R/'freeze.json')
        for n,h in frozen['sha256'].items():assert sha(R/n)==h,('Frozen file changed',n)
        schedule=load(R/'configs/schedule.json')
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]
    d=R/'results'/(a.phase+'-'+stamp);d.mkdir();r=Runner(C,d)
    proto={'phase':a.phase,'started_at_utc':utc(),'remote':remote,'configuration':C,'host':platform.platform(),'python':sys.version,'freeze_sha256':sha(R/'freeze.json') if a.phase=='formal' else None}
    save(d/'protocol.json',proto);save(d/'schedule.json',schedule);shutil.copyfile(__file__,d/'runner-version.py')
    if a.phase=='formal':save(R/'FORMAL_STARTED.json',{'session':str(d.relative_to(R)),'started_at_utc':utc()})
    samples=[];status={'status':'running','started_at_utc':utc()};save(d/'session-status.json',status)
    try:
        out,_,rec=r.shell('initial-hashes','sha256sum '+' '.join(dep['hashes']),d,90);must(rec)
        assert {x.split()[1]:x.split()[0] for x in out.decode().splitlines()}==dep['hashes']
        inventory(r,'cache-before',remote,d)
        for i,item in enumerate(schedule,1):
            item=dict(item,index=i)
            sample=run_sample(r,d/f'{i:03}-b{item["block"]:02}-{item["backend"]}-pp{item["pp"]}-tg{item["tg"]}',item,remote);samples.append(sample)
            if sample['status']!='success':raise RuntimeError('Stopped after explicit failure; no automatic replacement')
        status['status']='completed'
    except Exception as ex:status.update(status='failed',error=str(ex))
    inventory(r,'cache-after',remote,d)
    r.adb('pull-caches',['pull',remote+'/opencl/tmp',str(d/'gpu-cache-after')],d)
    status.update(ended_at_utc=utc(),attempted=len(samples),successful=sum(s['status']=='success' for s in samples));save(d/'session-status.json',status);print(json.dumps(status),flush=True)
    if status['status']!='completed':sys.exit(1)
if __name__=='__main__':main()
