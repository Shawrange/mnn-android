from pathlib import Path
import subprocess,json,hashlib
R=Path('/mnt/e/DUANCE/gate2-decode');S='/home/shawrange/src/MNN-3.6.2'
items=[]
for p in sorted((R/'evidence/source/clean').rglob('*')):
    if not p.is_file():continue
    name=p.relative_to(R/'evidence/source/clean').as_posix()
    raw=subprocess.check_output(['git','-C',S,'show','7e3c6fb5225d3ccf22807ee641332669df34650d:'+name])
    assert raw==p.read_bytes(),name
    items.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),'matches_fixed_commit':True})
(R/'evidence/source/snapshot-verification.json').write_text(json.dumps(items,indent=2))
print('Fixed-commit source snapshots matched:',len(items))
