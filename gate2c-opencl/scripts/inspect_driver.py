from run import R,C,REMOTE,Runner,must,save,utc
from pathlib import Path
import subprocess,hashlib
d=R/'evidence/driver-elf';d.mkdir(parents=True,exist_ok=True);r=Runner(C,d)
for name in ['libOpenCL.so','libOpenCL_adreno.so']:
    must(r.adb('pull-'+name,['pull','/vendor/lib64/'+name,str(d/name)],d)[2])
    cmd=['wsl','-d','Ubuntu','--','/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf','-h','-d','/mnt/e/DUANCE/gate2c-opencl/evidence/driver-elf/'+name]
    p=subprocess.run(cmd,capture_output=True);(d/(name+'.readelf.txt')).write_bytes(p.stdout);(d/(name+'.readelf.stderr.txt')).write_bytes(p.stderr);save(d/(name+'.inspection.json'),{'command':cmd,'exit_code':p.returncode,'sha256':hashlib.sha256((d/name).read_bytes()).hexdigest(),'checked_at_utc':utc()});assert p.returncode==0
profile=sorted((R/'results').glob('profile-*'))[-1];r=Runner(C,profile)
r.shell('llm-bench-help','cd '+REMOTE+'/profile && LD_LIBRARY_PATH=. ./llm_bench --help',profile)
