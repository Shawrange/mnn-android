from pathlib import Path
import argparse,hashlib,json,shlex,shutil,time,uuid
from adb_utils import Runner,load,save,utc
R=Path(__file__).resolve().parents[1]
C=load(R.parent/'mobile-llm-runtime-lab/configs/cpu.json');C.update(scope='Gate2-C0/C1 OpenCL feasibility only',remote_root='/data/local/tmp/mnn-gate2c-20261108')
REMOTE=C['remote_root'];MODEL='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN'
def must(rec):
    if rec['exit_code']:raise RuntimeError('Command failed: '+str(rec))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def probe(r,d):
    out,_,rec=r.adb('device',['get-state'],d);must(rec);assert out.strip()==b'device'
    must(r.shell('mkdir',f'mkdir -p {REMOTE}',d)[2])
    must(r.adb('push-probe',['push',str(R/'staging/cl_probe'),REMOTE+'/cl_probe'],d)[2]);must(r.shell('chmod',f'chmod 755 {REMOTE}/cl_probe',d)[2])
    r.shell('metadata','getprop ro.build.fingerprint; getprop ro.soc.model; getprop ro.hardware.egl; getprop ro.build.version.sdk; id; uname -a; getconf PAGESIZE',d)
    r.shell('library-inventory','ls -l /vendor/lib64/libOpenCL.so /vendor/lib64/libOpenCL*.so /vendor/lib64/libGLES*.so /vendor/lib64/egl/* /system/vendor/lib64/libOpenCL.so /system/lib64/libOpenCL.so; cat /vendor/etc/public.libraries.txt /system/etc/public.libraries.txt',d)
    r.state('state',d)
    results=[]
    for i,lib in enumerate(['libOpenCL.so','/vendor/lib64/libOpenCL.so']):
        out,err,rec=r.shell(f'opencl-probe-{i}',f'cd {REMOTE} && ./cl_probe {shlex.quote(lib)}',d,60)
        results.append({'library':lib,'exit_code':rec['exit_code'],'arithmetic_kernel_passed':rec['exit_code']==0 and b'output_correct=1' in out})
    save(d/'capability-summary.json',{'probes':results,'scope':'Standalone GPU arithmetic is not proof of LLM placement'})
def deploy(r,d,kind):
    local=R/'staging'/kind;remote=REMOTE+'/'+kind
    must(r.shell('mkdir',f'mkdir -p {remote}',d)[2])
    for n in ['llm_demo','llm_bench','libMNN.so']:
        must(r.adb('push-'+n,['push',str(local/n),remote+'/'+n],d)[2])
    must(r.shell('chmod',f'chmod 755 {remote}/llm_demo {remote}/llm_bench',d)[2])
    paths={remote+'/'+n:local/n for n in ['llm_demo','llm_bench','libMNN.so']}
    for n in ['llm.mnn','llm.mnn.weight','config.cpu.json','llm_config.json','tokenizer.txt']:paths[MODEL+'/'+n]=R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n
    out,_,rec=r.shell('hashes','sha256sum '+' '.join(paths),d,90);must(rec)
    got={line.split()[1]:line.split()[0] for line in out.decode().splitlines()};expected={n:sha(p) for n,p in paths.items()};assert got==expected
    save(d/'verified-assets.json',expected)
def smoke(r,d,kind):
    deploy(r,d,kind);remote=REMOTE+'/'+kind
    configs=R/'configs';configs.mkdir(exist_ok=True)
    conf=load(R.parent/'gate0/assets/Qwen3-0.6B-MNN/config.cpu.json')
    conf.update(llm_model=MODEL+'/llm.mnn',llm_weight=MODEL+'/llm.mnn.weight',backend_type='opencl',thread_num=4,precision='low',memory='low',power='normal',sampler_type='greedy',async_=False)
    conf.pop('async_',None);conf.update({'async':False,'reuse_kv':False,'use_mmap':False,'max_new_tokens':16,'tmp_path':'tmp','tokenizer_file':MODEL+'/tokenizer.txt'})
    # Copy required configs/tokenizer into this new directory; graph and weight stay pinned in the original model dir.
    save(d/'config.opencl.json',conf)
    for name,path in [('config.json',d/'config.opencl.json'),('llm_config.json',R.parent/'gate0/assets/Qwen3-0.6B-MNN/llm_config.json'),('tokenizer.txt',R.parent/'gate0/assets/Qwen3-0.6B-MNN/tokenizer.txt')]:
        must(r.adb('push-'+name,['push',str(path),remote+'/'+name],d)[2])
    prompt=d/'prompt.txt';prompt.write_text('请用中文简短解释什么是人工智能。\n',encoding='utf-8')
    must(r.adb('push-prompt',['push',str(prompt),remote+'/prompt.txt'],d)[2])
    r.state('before',d)
    command=f'cd {remote} && LD_LIBRARY_PATH=. /system/bin/timeout 300 ./llm_demo config.json prompt.txt 16 1'
    out,err,rec=r.shell('demo',command,d,320);r.state('after',d)
    save(d/'smoke-status.json',{'kind':kind,'demo_exit_code':rec['exit_code'],'started_at_utc':rec['started_at_utc'],'ended_at_utc':rec['ended_at_utc'],'runtime_verification_pending_analysis':True})
    must(rec)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['probe','clean','profile']);a=ap.parse_args()
    d=R/'results'/(a.phase+'-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True,exist_ok=False)
    r=Runner(C,d);save(d/'protocol.json',dict(C,phase=a.phase,started_at_utc=utc()));shutil.copyfile(__file__,d/'runner-version.py');status={'status':'running'}
    try:
        if a.phase=='probe':probe(r,d)
        else:smoke(r,d,a.phase)
        status['status']='completed'
    except Exception as e:status.update(status='failed',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
