from pathlib import Path
import argparse,shutil,subprocess,json,hashlib
a=argparse.ArgumentParser();a.add_argument('kind',choices=['clean','profile']);args=a.parse_args()
R=Path('/mnt/e/DUANCE/gate2c-opencl');S=Path('/home/shawrange/src/MNN-3.6.2')
b=S/('build-android-arm64-opencl-gate2c'+('-profile' if args.kind=='profile' else ''))
d=R/'evidence/build'/args.kind;d.mkdir(parents=True,exist_ok=True);stage=R/'staging'/args.kind;stage.mkdir(parents=True,exist_ok=True)
for n in ['configure.exit.txt','build.exit.txt']:assert (b/n).read_text().strip()=='0'
for p in b.iterdir():
    if p.is_file() and (p.suffix in ['.txt','.log'] or p.name=='binaries.sha256'):shutil.copyfile(p,d/p.name)
for n in ['llm_demo','llm_bench','libMNN.so']:shutil.copyfile(b/n,stage/n)
(d/'ninja-commands.txt').write_bytes(subprocess.check_output(['ninja','-C',str(b),'-t','commands']))
def cache(p):
    return {line.split(':',1)[0]:line.split('=',1)[1] for line in p.read_text().splitlines() if ':' in line and '=' in line and not line.startswith(('#','//'))}
cpu=cache(R.parent/'gate0/evidence/build/CMakeCache.txt');gpu=cache(b/'CMakeCache.txt')
(d/'cpu-cache-differences.json').write_text(json.dumps({k:{'cpu':cpu.get(k),'gpu':gpu.get(k)} for k in sorted(set(cpu)|set(gpu)) if cpu.get(k)!=gpu.get(k)},indent=2))
(d/'artifact-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},indent=2))
print('Staged',args.kind)
