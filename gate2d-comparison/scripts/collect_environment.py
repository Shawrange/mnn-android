"""Run inside WSL. Pin evidence to git show, capture build provenance."""
from pathlib import Path
import subprocess,json,hashlib,shutil
R=Path('/mnt/e/DUANCE/gate2d-comparison');S=Path('/home/shawrange/src/MNN-3.6.2');C='7e3c6fb5225d3ccf22807ee641332669df34650d'
files=['transformers/llm/engine/tools/llm_bench.cpp','transformers/llm/engine/src/llm.cpp','transformers/llm/engine/src/llmconfig.hpp','transformers/llm/engine/src/speculative_decoding/generate.cpp','transformers/llm/engine/include/llm/llm.hpp','source/backend/opencl/core/OpenCLBackend.cpp','source/backend/opencl/core/runtime/OpenCLRuntime.cpp','include/MNN/AutoTime.hpp','source/core/AutoTime.cpp','include/MNN/MNNForwardType.h']
manifest=[]
for n in files:
    raw=(S/n).read_bytes();assert raw==subprocess.check_output(['git','-C',str(S),'show',C+':'+n]);p=R/'evidence/source'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);manifest.append({'file':n,'sha256':hashlib.sha256(raw).hexdigest()})
(R/'evidence/source/manifest.json').write_text(json.dumps(manifest,indent=2))
state={'commit':subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD']).decode().strip(),'tracked_status':subprocess.check_output(['git','-C',str(S),'status','--porcelain','--untracked-files=no']).decode()};assert state['commit']==C and not state['tracked_status'];(R/'evidence/source-state.json').write_text(json.dumps(state,indent=2))
for b,orig in [('cpu','gate0/evidence/build'),('opencl','gate2c-opencl/evidence/build/clean')]:
    d=R/'evidence/build'/b;d.mkdir(parents=True)
    for n in ['CMakeCache.txt','build.ninja','configure.command.txt','inspection-summary.json']:
        p=R.parent/orig/n
        if p.exists():shutil.copyfile(p,d/n)
commands={'environment':['bash','-lc','/home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++ --version && cmake --version && ninja --version && cat /etc/os-release'],
 'elf':['bash','-lc','for b in cpu opencl; do /home/shawrange/Android/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf -h -d -l /mnt/e/DUANCE/gate2d-comparison/staging/$b/libMNN.so /mnt/e/DUANCE/gate2d-comparison/staging/$b/llm_bench; done']}
for label,cmd in commands.items():
    p=subprocess.run(cmd,capture_output=True);(R/'evidence'/f'{label}.stdout.txt').write_bytes(p.stdout);(R/'evidence'/f'{label}.stderr.txt').write_bytes(p.stderr);(R/'evidence'/f'{label}.command.json').write_text(json.dumps({'command':cmd,'exit_code':p.returncode},indent=2));assert p.returncode==0
print('Source snapshots and clean build provenance captured')
