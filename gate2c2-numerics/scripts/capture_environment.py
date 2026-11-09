from run import *
import subprocess,platform
d=R/'evidence/environment';d.mkdir(parents=True,exist_ok=True);r=Runner(C,d)
r.shell('device','id; getprop ro.build.fingerprint; getprop ro.soc.model; getprop ro.build.version.release; getprop ro.build.version.sdk; uname -a; getconf PAGESIZE; getenforce; ps -A | grep -E "numeric_probe|replay"',d)
r.state('state',d)
save(d/'host.json',{'platform':platform.platform(),'python':platform.python_version(),'commit':C['mnn_commit'],'model_revision':C['model_revision'],'timestamp_utc':utc()})
records=[]
for p in sorted((R/'results').glob('*/protocol.json')):
    session=p.parent;proto=load(p);remote=proto.get('remote','/data/local/tmp/mnn-gate2c2-'+session.name)
    tool='replay' if session.name.startswith('replay-') else 'numeric_probe'
    # Preserve each historical diagnostic executable, including failed/invalid versions.
    dest=session/'executable-evidence';dest.mkdir(exist_ok=True)
    must(r.adb('pull-executable',['pull',remote+'/cpu/'+tool,str(dest/tool)],dest)[2])
    args=[remote+'/'+b+'/'+name for b in ['cpu','opencl'] for name in ['libMNN.so',tool]]
    out,_,rec=r.shell('phone-hashes','sha256sum '+' '.join(args),dest);must(rec)
    actual={line.split()[1]:line.split()[0] for line in out.decode().splitlines()}
    for b in ['cpu','opencl']:
        expected_lib=R.parent/('gate0/staging/libMNN.so' if b=='cpu' else 'gate2c-opencl/staging/clean/libMNN.so')
        assert actual[remote+'/'+b+'/libMNN.so']==sha(expected_lib)
        assert actual[remote+'/'+b+'/'+tool]==sha(dest/tool)
    records.append({'session':session.name,'remote':remote,'hashes':actual})
save(d/'device-artifacts.json',records)
cmd='cd /home/shawrange/src/MNN-3.6.2 && git rev-parse HEAD && git status --porcelain --untracked-files=no && /home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++ --version && cmake --version && ninja --version && cat /etc/os-release'
command=['wsl','-d','Ubuntu','--','bash','-lc',cmd]
result=subprocess.run(command,capture_output=True);(d/'wsl.stdout.txt').write_bytes(result.stdout);(d/'wsl.stderr.txt').write_bytes(result.stderr);save(d/'wsl.command.json',{'command':command,'exit_code':result.returncode})
assert result.returncode==0
print('Environment and',len(records),'device binary versions verified')
