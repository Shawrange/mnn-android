from pathlib import Path
import argparse,hashlib,json,shlex,time,uuid,shutil
from adb_utils import Runner,load,save,utc
R=Path(__file__).resolve().parents[1]
C=load(R.parent/'mobile-llm-runtime-lab/configs/cpu.json')
C={k:C[k] for k in ['adb','serial','mnn_commit','model_revision']}
MODEL='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def must(rec):
    if rec['exit_code']:raise RuntimeError('Command failed: '+str(rec))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['pilot','low','high','checkpoints']);a=ap.parse_args()
    d=R/'results'/(a.phase+'-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True)
    remote='/data/local/tmp/mnn-gate2c2-'+d.name;r=Runner(C,d)
    save(d/'protocol.json',dict(C,phase=a.phase,started_at_utc=utc(),remote=remote,model=MODEL,scope='Numerical diagnostics only'))
    for p in [Path(__file__),R/'protocol.md',R/'scripts/numeric_probe.cpp']:shutil.copyfile(p,d/p.name)
    status={'status':'running','runs':[]}
    try:
        must(r.adb('device',['get-state'],d)[2])
        must(r.shell('mkdir','mkdir -p '+remote,d)[2])
        libs={'cpu':R.parent/'gate0/staging/libMNN.so','opencl':R.parent/'gate2c-opencl/staging/clean/libMNN.so'}
        expected={}
        for backend,lib in libs.items():
            dest=remote+'/'+backend;must(r.shell('mkdir-'+backend,'mkdir -p '+dest,d)[2])
            for name,p in [('libMNN.so',lib),('numeric_probe',R/'staging/numeric_probe')]:
                must(r.adb('push-'+backend+'-'+name,['push',str(p),dest+'/'+name],d)[2]);expected[dest+'/'+name]=sha(p)
            must(r.shell('chmod-'+backend,'chmod 755 '+dest+'/numeric_probe',d)[2])
        out,_,rec=r.shell('hashes','sha256sum '+' '.join(expected)+' '+MODEL+'/llm.mnn '+MODEL+'/llm.mnn.weight',d,90);must(rec)
        got={line.split()[1]:line.split()[0] for line in out.decode().splitlines()}
        for p,h in expected.items():assert got[p]==h
        for n in ['llm.mnn','llm.mnn.weight']:assert got[MODEL+'/'+n]==sha(R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n)
        save(d/'verified-assets.json',got)
        specs=[]
        if a.phase=='pilot':specs=[(b,'low','synthetic','checkpoints',0) for b in libs]
        elif a.phase=='low':specs=[(b,'low',k,'off',i) for i in range(2) for k in ['synthetic','natural'] for b in libs]
        elif a.phase=='high':specs=[(b,'high',k,'off',0) for k in ['synthetic','natural'] for b in libs]
        else:specs=[(b,p,k,'checkpoints',0) for p in ['low','high'] for k in ['synthetic','natural'] for b in libs]
        for backend,precision,kind,mode,process in specs:
            name=f'{backend}-{precision}-{kind}-{mode}-p{process}';p=d/name;p.mkdir()
            work=remote+'/'+name;must(r.shell('mkdir','mkdir -p '+work+'/out',p)[2]);r.state('before',p)
            command='cd '+work+' && LD_LIBRARY_PATH='+remote+'/'+backend+' /system/bin/timeout 180 '+remote+'/'+backend+'/numeric_probe '+shlex.join([MODEL+'/config.cpu.json',backend,precision,kind,mode,work+'/out/sample','2'])
            out,err,rec=r.shell('run',command,p,200);r.state('after',p)
            # Pull partial outputs even on failure. No failed case enters valid analyses.
            r.adb('pull',['pull',work+'/out',str(p)],p,60)
            result=dict(backend=backend,precision=precision,kind=kind,mode=mode,process=process,exit_code=rec['exit_code'],directory=str(p.relative_to(R)),valid=False)
            if rec['exit_code']==0 and (p/'out/sample.summary.json').exists():
                result['valid']=not any(x in out+err for x in [b'[Error]',b'Build program failed',b'CANNOT LINK'])
            status['runs'].append(result);save(p/'result.json',result);save(d/'session-status.json',status)
            if not result['valid']:raise RuntimeError('Invalid diagnostic run: '+name)
            print('Completed',name,flush=True)
        status['status']='completed'
    except Exception as e:status.update(status='failed',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
