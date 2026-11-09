from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];out=R/'evidence/prior-stage-hashes.json'
assert not out.exists(),'Do not replace the pre-experiment preservation snapshot'
hashes={}
for folder in ['gate0','mobile-llm-runtime-lab','gate2-decode']:
    for p in (R.parent/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            with p.open('rb') as f:hashes[str(p.relative_to(R.parent))]=hashlib.file_digest(f,'sha256').hexdigest()
out.write_text(json.dumps(hashes,indent=2,ensure_ascii=False),encoding='utf-8')
print('Preserved hashes:',len(hashes))
