from run import *
def main():
    d=R/'results'/('replay-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True)
    remote='/data/local/tmp/mnn-gate2c2-'+d.name;r=Runner(C,d)
    save(d/'protocol.json',{'started_at_utc':utc(),'model':MODEL,'scope':'Original graph first Q projection Tensor Path; identical CPU Low input; not performance'})
    shutil.copyfile(__file__,d/'runner.py');shutil.copyfile(R/'scripts/replay.cpp',d/'replay.cpp');shutil.copyfile(R/'protocol.md',d/'protocol.md')
    status={'status':'running','runs':[]}
    try:
        libs={'cpu':R.parent/'gate0/staging/libMNN.so','opencl':R.parent/'gate2c-opencl/staging/clean/libMNN.so'}
        for backend,lib in libs.items():
            dest=remote+'/'+backend;must(r.shell('mkdir-'+backend,'mkdir -p '+dest,d)[2])
            for name,p in [('libMNN.so',lib),('replay',R/'staging/replay')]:must(r.adb('push-'+backend+'-'+name,['push',str(p),dest+'/'+name],d)[2])
            must(r.shell('chmod-'+backend,'chmod 755 '+dest+'/replay',d)[2])
        parent=sorted((R/'results').glob('checkpoints-*'))[-1]
        for kind in ['synthetic','natural']:
            original=parent/f'cpu-low-{kind}-checkpoints-p0/out/sample.r0.q_input.f32'
            ids=load(parent/f'cpu-low-{kind}-checkpoints-p0/out/sample.ids.json')
            for backend,precision,memory in [('cpu','low','low'),('opencl','low','low'),('cpu','high','low'),('opencl','high','low'),('cpu','high','high')]:
                name=f'{backend}-{precision}-mem{memory}-{kind}';p=d/name;p.mkdir();work=remote+'/'+name
                must(r.shell('mkdir','mkdir -p '+work+'/out',p)[2]);must(r.adb('push-input',['push',str(original),work+'/input.f32'],p)[2])
                save(p/'input-source.json',{'file':str(original.relative_to(R)),'sha256':sha(original),'batch':len(ids)})
                r.state('before',p)
                command='cd '+work+' && LD_LIBRARY_PATH='+remote+'/'+backend+' /system/bin/timeout 90 '+remote+'/'+backend+'/replay '+shlex.join([MODEL+'/llm.mnn',backend,precision,memory,work+'/input.f32',work+'/out/sample',str(len(ids))])
                out,err,rec=r.shell('run',command,p,110);r.state('after',p);r.adb('pull',['pull',work+'/out',str(p)],p)
                result=dict(backend=backend,precision=precision,memory=memory,kind=kind,exit_code=rec['exit_code'],valid=rec['exit_code']==0 and (p/'out/sample.meta.json').exists())
                save(p/'result.json',result);status['runs'].append(result)
                if not result['valid']:raise RuntimeError('Replay failed: '+name)
                print('Completed',name,flush=True)
        status['status']='completed'
    except Exception as e:status.update(status='failed',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
