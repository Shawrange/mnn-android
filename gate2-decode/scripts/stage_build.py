from pathlib import Path
import shutil,subprocess,json,hashlib
b=Path('/home/shawrange/src/MNN-decode-gate2a/build-gate2');r=Path('/mnt/e/DUANCE/gate2-decode')
for p in b.iterdir():
    if p.is_file() and (p.suffix in ['.txt','.log'] or p.name=='binaries.sha256'):
        shutil.copyfile(p,r/'evidence/build'/p.name)
for n in ['llm_demo','llm_bench','libMNN.so']:shutil.copyfile(b/n,r/'staging'/n)
state={}
for name,path in [('clean','/home/shawrange/src/MNN-3.6.2'),('diagnostic','/home/shawrange/src/MNN-decode-gate2a')]:
    state[name]={k:subprocess.check_output(['git','-C',path,*args]).decode() for k,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain','--untracked-files=no'])]}
(r/'evidence/build/source-state.json').write_text(json.dumps(state,indent=2))
(r/'evidence/build/staging-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'staging').iterdir()},indent=2))
