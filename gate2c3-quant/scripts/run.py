from pathlib import Path
import json,hashlib,time,uuid,shutil,shlex
from adb_utils import Runner,load,save,utc
R=Path(__file__).resolve().parents[1]
prior=load(R.parent/'mobile-llm-runtime-lab/configs/cpu.json');C={k:prior[k] for k in ['adb','serial','mnn_commit','model_revision']}
MODEL='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def must(rec):
    if rec['exit_code']:raise RuntimeError('Command failed: '+str(rec))
def main():
    d=R/'results'/('q-only-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True)
    remote='/data/local/tmp/mnn-gate2c3-'+d.name;r=Runner(C,d);save(d/'protocol.json',dict(C,started_at_utc=utc(),remote=remote,scope='First Q projection independent quantization validation'))
    for p in [Path(__file__),R/'scripts/replay.cpp',R/'protocol.md']:shutil.copyfile(p,d/p.name)
    status={'status':'running','runs':[]}
    try:
        libs={'cpu':R.parent/'gate0/staging/libMNN.so','diagnostic':R/'staging/libMNN-diagnostic.so','opencl':R.parent/'gate2c-opencl/staging/clean/libMNN.so'}
        expected={}
        for name,lib in libs.items():
            dest=remote+'/'+name;must(r.shell('mkdir-'+name,'mkdir -p '+dest,d)[2])
            for n,p in [('libMNN.so',lib),('replay',R/'staging/replay')]:must(r.adb('push-'+name+'-'+n,['push',str(p),dest+'/'+n],d)[2]);expected[dest+'/'+n]=sha(p)
            must(r.shell('chmod-'+name,'chmod 755 '+dest+'/replay',d)[2])
        out,_,rec=r.shell('hashes','sha256sum '+' '.join(expected)+' '+MODEL+'/llm.mnn '+MODEL+'/llm.mnn.weight',d,90);must(rec)
        actual={x.split()[1]:x.split()[0] for x in out.decode().splitlines()};assert all(actual[k]==v for k,v in expected.items())
        for n in ['llm.mnn','llm.mnn.weight']:assert actual[MODEL+'/'+n]==sha(R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n)
        save(d/'verified-assets.json',actual)
        source=R.parent/'gate2c2-numerics/results/checkpoints-20261108T202929Z-254d02'
        for kind,n in [('synthetic',8),('natural',13)]:
            src=source/f'cpu-low-{kind}-checkpoints-p0/out/sample.r0.q_input.f32'
            for name,lib,backend,precision,memory,trace in [('cpu-low','cpu','cpu','low','low',False),('diag-off','diagnostic','cpu','low','low',False),('diag-on','diagnostic','cpu','low','low',True),('cpu-float','cpu','cpu','high','high',False),('gpu-high','opencl','opencl','high','low',False)]:
                p=d/(kind+'-'+name);p.mkdir();work=remote+'/'+p.name
                must(r.shell('mkdir','mkdir -p '+work+'/out',p)[2]);must(r.adb('push-input',['push',str(src),work+'/input.f32'],p)[2]);save(p/'input-source.json',{'file':str(src.relative_to(R.parent)),'sha256':sha(src),'batch':n})
                r.state('before',p)
                env=('MNN_GATEC3_PREFIX='+work+'/out/trace ' if trace else '')+'LD_LIBRARY_PATH='+remote+'/'+lib
                command='cd '+work+' && '+env+' /system/bin/timeout 90 '+remote+'/'+lib+'/replay '+shlex.join([MODEL+'/llm.mnn',backend,precision,memory,work+'/input.f32',work+'/out/sample',str(n)])
                out,err,rec=r.shell('run',command,p,110);r.state('after',p);r.adb('pull',['pull',work+'/out',str(p)],p,90)
                result={'kind':kind,'mode':name,'backend':backend,'precision':precision,'memory':memory,'trace':trace,'exit_code':rec['exit_code'],'valid':False}
                if rec['exit_code']==0 and (p/'out/sample.meta.json').exists():
                    meta=load(p/'out/sample.meta.json');result['valid']=len(meta['runs'])==3 and all(x['exit_code']==0 for x in meta['runs'])
                save(p/'result.json',result);status['runs'].append(result)
                if not result['valid']:raise RuntimeError('Invalid Q run: '+p.name)
                print('Completed',p.name,flush=True)
        status['status']='completed'
    except Exception as e:status.update(status='failed',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
