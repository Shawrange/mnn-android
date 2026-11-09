"""Read-only final project manifest check. Never launches phone inference."""
from pathlib import Path
import hashlib,json,sys
R=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    marker=json.loads((R/'PROJECT_FREEZE.json').read_text(encoding='utf-8'))
    assert marker['status']=='frozen' and marker['formal_gate2d_processes']==36
    assert sha(R/'project-manifest.json')==marker['project_manifest_sha256']
    manifest=json.loads((R/'project-manifest.json').read_text(encoding='utf-8'))
    bad=[n for n,h in manifest['sha256'].items() if not (R/n).is_file() or sha(R/n)!=h]
    if bad:print(json.dumps({'status':'failed','changed_or_missing':bad},ensure_ascii=False));return 1
    print(json.dumps({'status':'verified','frozen_at_utc':marker['frozen_at_utc'],'files':len(manifest['sha256']),'formal_gate2d_processes':36,'new_inference_launched':False},ensure_ascii=False));return 0
if __name__=='__main__':sys.exit(main())
