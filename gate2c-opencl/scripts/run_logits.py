from pathlib import Path
import time,uuid,shlex
from run import R,C,REMOTE,MODEL,Runner,save,utc,must
d=R/'results'/('logits-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True,exist_ok=False);r=Runner(C,d)
save(d/'protocol.json',{'scope':'Two small prefill-only numerical capability probes; not a performance baseline','model':MODEL,'criteria_file':'GPU正确性对照计划.md','started_at_utc':utc()})
status={'status':'running'}
try:
    for mode in ['cpu','opencl']:
        remote=REMOTE+'/oracle-'+mode;must(r.shell('mkdir-'+mode,'mkdir -p '+remote,d)[2])
        local=R.parent/'gate0/staging/libMNN.so' if mode=='cpu' else R/'staging/clean/libMNN.so'
        for n,p in [('libMNN.so',local),('logits_probe',R/'staging/logits_probe')]:must(r.adb('push-'+mode+'-'+n,['push',str(p),remote+'/'+n],d)[2])
        must(r.shell('chmod-'+mode,'chmod 755 '+remote+'/logits_probe',d)[2])
        for kind in ['synthetic','natural']:
            p=d/(mode+'-'+kind);p.mkdir();prefix=remote+'/'+d.name+'-'+kind
            r.state('before',p)
            out,err,rec=r.shell('prefill','cd '+remote+' && LD_LIBRARY_PATH=. /system/bin/timeout 180 ./logits_probe '+shlex.join([MODEL+'/config.cpu.json',mode,kind,prefix]),p,200)
            r.state('after',p);must(rec)
            for suffix in ['ids.txt','logits.f32','meta.txt','config.json']:must(r.adb('pull-'+suffix,['pull',prefix+'.'+suffix,str(p/suffix)],p)[2])
    status['status']='completed'
except Exception as e:status.update(status='failed',error=str(e));raise
finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
print(d)
