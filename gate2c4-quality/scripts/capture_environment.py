from run import *
import subprocess,platform
d=R/'evidence/environment';d.mkdir(parents=True,exist_ok=True);r=Runner(C,d)
r.shell('device','id; getprop ro.build.fingerprint; getprop ro.soc.model; getprop ro.build.version.release; getprop ro.build.version.sdk; uname -a; getconf PAGESIZE; getenforce',d)
r.state('state',d);save(d/'host.json',{'platform':platform.platform(),'python':platform.python_version(),'mnn_commit':C['mnn_commit'],'model_revision':C['model_revision'],'captured_at_utc':utc()})
records=[]
for p in sorted((R/'results').glob('*/protocol.json')):
    proto=load(p);recorded=load(p.parent/'verified-assets.json');paths=[k for k in recorded if k.startswith(proto['remote']+'/')]
    sub=d/p.parent.name;sub.mkdir(exist_ok=True);out,_,rec=r.shell('final-hashes','sha256sum '+' '.join(paths),sub,90);must(rec)
    actual={x.split()[1]:x.split()[0] for x in out.decode().splitlines()};assert all(actual[k]==recorded[k] for k in actual)
    records.append({'session':p.parent.name,'hashes':actual})
save(d/'final-device-artifacts.json',records)
cmd=['wsl','-d','Ubuntu','--','bash','-lc','/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++ --version && cmake --version && ninja --version && cat /etc/os-release']
p=subprocess.run(cmd,capture_output=True);(d/'wsl.stdout.txt').write_bytes(p.stdout);(d/'wsl.stderr.txt').write_bytes(p.stderr);save(d/'wsl.command.json',{'command':cmd,'exit_code':p.returncode});assert p.returncode==0
print('Captured environment and verified',len(records),'session deployments')
