"""Read-only final project manifest check. Never launches phone inference."""
from pathlib import Path
import argparse,hashlib,json,sys
R=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--available',action='store_true',help='Permit only explicitly omitted download/cache files to be absent');args=parser.parse_args()
    marker=json.loads((R/'PROJECT_FREEZE.json').read_text(encoding='utf-8'))
    assert marker['status']=='frozen' and marker['formal_gate2d_processes']==36
    assert sha(R/'project-manifest.json')==marker['project_manifest_sha256']
    manifest=json.loads((R/'project-manifest.json').read_text(encoding='utf-8'))
    publication_path=R/'publication/publication.json'
    publication=json.loads(publication_path.read_text(encoding='utf-8')) if publication_path.exists() else {}
    overrides=publication.get('frozen_path_overrides',{});omitted=set(publication.get('omitted_from_git',[]))
    bad=[];skipped=[]
    for name,h in manifest['sha256'].items():
        p=R/overrides.get(name,name)
        if args.available and not p.is_file() and name in omitted:skipped.append(name);continue
        if not p.is_file() or sha(p)!=h:bad.append(name)
    for name,h in publication.get('updated_sha256',{}).items():
        if not (R/name).is_file() or sha(R/name)!=h:bad.append(name)
    if bad:print(json.dumps({'status':'failed','changed_or_missing':bad},ensure_ascii=False));return 1
    print(json.dumps({'status':'verified_available' if skipped else 'verified','frozen_at_utc':marker['frozen_at_utc'],'files_checked':len(manifest['sha256'])-len(skipped),'omitted_external_or_cache_files':len(skipped),'updated_documents_checked':len(publication.get('updated_sha256',{})),'formal_gate2d_processes':36,'new_inference_launched':False},ensure_ascii=False));return 0
if __name__=='__main__':sys.exit(main())
