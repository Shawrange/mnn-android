from pathlib import Path
import subprocess,shutil,hashlib,json
R=Path('/mnt/e/DUANCE/gate2c3-quant');S=Path('/home/shawrange/src/MNN-quant-gate2c3');B=S/'build-android-arm64-cpu-gate2c3'
d=R/'evidence/build';d.mkdir(parents=True,exist_ok=True)
for name in ['configure.command.txt','configure.log','configure.exit.txt','build.command.txt','build.log','build.exit.txt','build-environment.txt','CMakeCache.txt','cmake-cache-summary.txt','libMNN.so.readelf.txt','binaries.sha256']:
    shutil.copyfile(B/name,d/name)
assert (d/'build.exit.txt').read_text().strip()=='0'
shutil.copyfile(B/'libMNN.so',R/'staging/libMNN-diagnostic.so')
nm='/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-nm'
(d/'symbols.txt').write_bytes(subprocess.check_output([nm,'-anC',str(B/'libMNN.so')]))
(d/'ninja-commands.txt').write_bytes(subprocess.check_output(['ninja','-C',str(B),'-t','commands']))
patch=subprocess.check_output(['git','-C',str(S),'diff','--binary'])
patch+=subprocess.run(['git','-C',str(S),'diff','--no-index','--binary','--','/dev/null','source/backend/cpu/compute/GateC3Capture.hpp'],capture_output=True).stdout
(R/'evidence/diagnostic.patch').write_bytes(patch)
(R/'evidence/branch-state.txt').write_bytes(subprocess.check_output(['git','-C',str(S),'status','--short']))
(R/'evidence/build/artifacts.json').write_text(json.dumps({str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [R/'staging/libMNN-diagnostic.so',R/'staging/replay',R/'evidence/diagnostic.patch']},indent=2))
print('Staged diagnostics, symbols and branch patch')
