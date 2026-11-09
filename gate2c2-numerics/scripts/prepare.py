from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[1]
R.joinpath('evidence').mkdir(exist_ok=True)
out=R/'evidence/prior-hashes.json'
assert not out.exists(),'Never replace protection snapshot'
items={}
for name in ['gate0','mobile-llm-runtime-lab','gate2-decode','gate2b-decode-hotspots','gate2c-opencl']:
    for p in (R.parent/name).rglob('*'):
        if p.is_file():
            with p.open('rb') as f: items[str(p.relative_to(R.parent))]=hashlib.file_digest(f,'sha256').hexdigest()
out.write_text(json.dumps(items,indent=2),encoding='utf-8')
shutil.copyfile(R.parent/'gate2c-opencl/scripts/adb_utils.py',R/'scripts/adb_utils.py')
print('Protected files:',len(items))
