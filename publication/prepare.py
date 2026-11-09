"""Prepare the GitHub publication record without changing frozen evidence."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,subprocess
R=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
manifest=json.loads((R/'project-manifest.json').read_text(encoding='utf-8'))
overrides={'README.md':'publication/frozen/README.md','verify_project.py':'publication/frozen/verify_project.py'}
for old,new in overrides.items():assert sha(R/new)==manifest['sha256'][old]
names=list(manifest['sha256'])
p=subprocess.run(['git','check-ignore','--stdin','-z'],input=('\0'.join(names)+'\0').encode('utf-8'),capture_output=True,cwd=R)
assert p.returncode in [0,1]
omitted=sorted(x for x in p.stdout.decode('utf-8').split('\0') if x)
updates=['README.md','verify_project.py','.gitignore','.gitattributes','THIRD_PARTY_NOTICES.md','publication/README.md','publication/prepare.py']
data={'repository':'https://github.com/Shawrange/mnn-android','created_at_utc':datetime.now(timezone.utc).isoformat(),'change_scope':'GitHub presentation and packaging only; no inference, model or experiment changes',
      'original_project_manifest_sha256':sha(R/'project-manifest.json'),'frozen_path_overrides':overrides,'updated_sha256':{n:sha(R/n) for n in updates},'omitted_from_git':omitted}
(R/'publication/publication.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=[R/x.decode('utf-8') for x in subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=R).split(b'\0') if x]
large=[str(p.relative_to(R)) for p in files if p.stat().st_size>=100*1024**2];assert not large,large
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{35,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)')
suspects=[]
for p in files:
    if p.suffix.lower() not in {'.txt','.json','.py','.sh','.md','.log','.cpp','.hpp','.h','.yaml','.yml'}:continue
    raw=p.read_bytes()
    if b'\0' in raw:continue
    if pattern.search(raw):suspects.append(p.relative_to(R).as_posix())
assert not suspects,('Credential pattern requires review; values not printed',suspects)
print(json.dumps({'publication_files':len(files),'payload_MiB':round(sum(p.stat().st_size for p in files)/1024**2,2),'omitted_frozen_files':len(omitted),'files_over_100MiB':large,'credential_pattern_matches':suspects},ensure_ascii=False))
