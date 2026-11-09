from pathlib import Path
import argparse,json,hashlib,time,uuid,shutil,shlex,random,re
from adb_utils import Runner,load,save,utc
from score import grade
R=Path(__file__).resolve().parents[1]
old=load(R.parent/'mobile-llm-runtime-lab/configs/cpu.json');C={k:old[k] for k in ['adb','serial','mnn_commit','model_revision']}
MODEL='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def must(rec):
    if rec['exit_code']:raise RuntimeError(str(rec))
def check_freeze():
    f=load(R/'freeze.json')
    for path,h in f['sha256'].items():assert sha(R/path)==h,('Frozen file changed',path)
    return f
def deploy(r,d,remote,profile=False):
    libs={'cpu':R.parent/'gate0/staging/libMNN.so','opencl':R.parent/'gate2c-opencl/staging/clean/libMNN.so'}
    if profile:libs={'profile':R.parent/'gate2c-opencl/staging/profile/libMNN.so'}
    expected={}
    for backend,lib in libs.items():
        dest=remote+'/'+backend;must(r.shell('mkdir-'+backend,'mkdir -p '+dest,d)[2])
        for name,p in [('libMNN.so',lib),('quality_probe',R/'staging/quality_probe'),('runtime.json',R/'configs/runtime.json')]:
            must(r.adb('push-'+backend+'-'+name,['push',str(p),dest+'/'+name],d)[2]);expected[dest+'/'+name]=sha(p)
        must(r.shell('chmod-'+backend,'chmod 755 '+dest+'/quality_probe',d)[2])
    for name in ['llm.mnn','llm.mnn.weight','tokenizer.txt','llm_config.json','config.cpu.json']:expected[MODEL+'/'+name]=sha(R.parent/'gate0/assets/Qwen3-0.6B-MNN'/name)
    out,_,rec=r.shell('asset-hashes','sha256sum '+' '.join(expected),d,90);must(rec)
    actual={x.split()[1]:x.split()[0] for x in out.decode().splitlines()};assert expected==actual;save(d/'verified-assets.json',actual)
def run_case(r,d,remote,backend,case,mode='generate'):
    p=d/(case['id']+'-'+backend);p.mkdir(exist_ok=False);dest=remote+'/'+backend;outdir=dest+'/'+case['id']
    save(p/'request.json',case);must(r.shell('mkdir','mkdir -p '+outdir,p)[2]);must(r.adb('push-request',['push',str(p/'request.json'),outdir+'/request.json'],p)[2])
    command='cd '+dest+' && LD_LIBRARY_PATH=. /system/bin/timeout 180 ./quality_probe '+shlex.join([MODEL+'/config.cpu.json','opencl' if backend=='profile' else backend,'runtime.json',outdir+'/request.json',outdir+'/sample',mode])
    out,err,rec=r.shell('run',command,p,200)
    r.adb('pull',['pull',outdir,str(p/'device')],p,60)
    files=p/'device';meta=load(files/'sample.meta.json') if (files/'sample.meta.json').exists() else {'status':4,'stopped':False}
    raw=(files/'sample.text.txt').read_bytes() if (files/'sample.text.txt').exists() else b''
    try:text=raw.decode('utf-8');utf8=True
    except UnicodeDecodeError:text=raw.decode('utf-8',errors='replace');utf8=False
    runtime_ok=rec['exit_code']==0 and not re.search(rb'\[Error\]|Build program failed|CANNOT LINK|Can.t Find type=3|Init OpenCL Error',out+err) and (files/'sample.meta.json').exists()
    result=dict(meta,process_exit=rec['exit_code'],runtime_ok=bool(runtime_ok),raw_text=text,valid_utf8=utf8,backend=backend)
    save(p/'result.json',result)
    if mode=='generate':save(p/'score.json',grade(case,result))
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['pilot','formal','gpu-evidence']);args=ap.parse_args()
    frozen=check_freeze() if args.phase!='pilot' else None
    data=R/'datasets'/('pilot.jsonl' if args.phase=='pilot' else 'formal.jsonl');cases=[json.loads(x) for x in data.read_text(encoding='utf-8').splitlines()]
    d=R/'results'/(args.phase+'-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True)
    remote='/data/local/tmp/mnn-gate2c4-'+d.name;r=Runner(C,d)
    schedule=[]
    if args.phase=='gpu-evidence':schedule=[(cases[0],'profile')]
    else:
        order=cases.copy();random.Random(42024).shuffle(order)
        for i,c in enumerate(order):schedule += [(c,b) for b in (['cpu','opencl'] if i%2==0 else ['opencl','cpu'])]
    save(d/'protocol.json',dict(C,phase=args.phase,remote=remote,started_at_utc=utc(),dataset_sha256=sha(data),freeze_sha256=sha(R/'freeze.json') if frozen else None))
    save(d/'schedule.json',[{'id':c['id'],'backend':b} for c,b in schedule]);shutil.copyfile(__file__,d/'runner.py');shutil.copyfile(R/'scripts/quality_probe.cpp',d/'quality_probe.cpp');shutil.copyfile(data,d/'dataset.jsonl')
    status={'status':'running','expected_runs':len(schedule),'completed_runs':0,'runtime_failures':[]}
    try:
        deploy(r,d,remote,args.phase=='gpu-evidence');r.state('before',d)
        r.shell('cache-before','find '+remote+' -maxdepth 2 -type f -name "*cache*" -exec ls -l {} \;',d)
        for i,(case,backend) in enumerate(schedule):
            result=run_case(r,d,remote,backend,case)
            if not result['runtime_ok']:status['runtime_failures'].append({'id':case['id'],'backend':backend,'exit_code':result['process_exit']})
            status['completed_runs']=i+1;save(d/'session-status.json',status)
            if (i+1)%10==0 or args.phase!='formal':print(f"Completed {i+1}/{len(schedule)} {case['id']} {backend}",flush=True)
            if (i+1)%20==0:r.state(f'state-{i+1:03}',d)
        r.state('after',d);r.shell('cache-after','find '+remote+' -maxdepth 2 -type f -name "*cache*" -exec ls -l {} \;',d)
        status['status']='completed'
    except Exception as e:status.update(status='interrupted',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
