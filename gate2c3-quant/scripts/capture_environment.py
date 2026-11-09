from run import *
import subprocess,platform,numpy as np
d=R/'evidence/environment';d.mkdir(parents=True,exist_ok=True);r=Runner(C,d)
r.shell('device','id; getprop ro.build.fingerprint; getprop ro.soc.model; getprop ro.build.version.release; uname -a; getenforce; ps -A | grep -E "replay|numeric_probe"',d)
r.state('state',d)
save(d/'host.json',{'platform':platform.platform(),'python':platform.python_version(),'numpy':np.__version__,'mnn_commit':C['mnn_commit'],'model_revision':C['model_revision'],'timestamp_utc':utc()})
session=sorted((R/'results').glob('q-only-*'))[-1];remote=load(session/'protocol.json')['remote']
files=[remote+'/'+name+'/'+file for name in ['cpu','diagnostic','opencl'] for file in ['libMNN.so','replay']]
out,_,rec=r.shell('final-device-hashes','sha256sum '+' '.join(files),d);must(rec)
actual={x.split()[1]:x.split()[0] for x in out.decode().splitlines()};recorded=load(session/'verified-assets.json');assert all(actual[k]==recorded[k] for k in actual)
save(d/'final-device-hashes.json',actual)
command=['wsl','-d','Ubuntu','--','bash','-lc','/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++ --version && g++ --version && cmake --version && ninja --version && cat /etc/os-release']
p=subprocess.run(command,capture_output=True);(d/'wsl.stdout.txt').write_bytes(p.stdout);(d/'wsl.stderr.txt').write_bytes(p.stderr);save(d/'wsl.command.json',{'command':command,'exit_code':p.returncode});assert p.returncode==0
print('Recorded environment and final phone binary hashes')
