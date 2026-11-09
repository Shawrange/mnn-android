from pathlib import Path
import hashlib
import json
import time
import urllib.request

root=Path(__file__).resolve().parent
evidence=root/'evidence/model-download'
evidence.mkdir(parents=True,exist_ok=True)
lock_path=root/'evidence/model/model-lock.json'
lock=json.loads(lock_path.read_text(encoding='utf-8'))
destination=root/'assets/Qwen3-0.6B-MNN'
destination.mkdir(parents=True,exist_ok=True)
records=[]
for entry in lock['files']:
    name=entry['path']
    path=destination/name
    url=f'https://huggingface.co/{lock["repo_id"]}/resolve/{lock["revision"]}/{name}'
    print(f'Downloading {name} from fixed revision {lock["revision"]}',flush=True)
    start=time.time()
    if not path.exists():
        partial=path.with_suffix(path.suffix+'.part')
        with urllib.request.urlopen(url,timeout=60) as response,partial.open('wb') as output:
            total=0
            threshold=64*1024*1024
            while block:=response.read(1024*1024):
                output.write(block)
                total+=len(block)
                if total>=threshold:
                    print(f'{name}: {total}/{entry["expected_size"]} bytes',flush=True)
                    threshold+=64*1024*1024
        partial.replace(path)
    size=path.stat().st_size
    assert size==entry['expected_size'],(name,size,entry['expected_size'])
    with path.open('rb') as f:
        sha256=hashlib.file_digest(f,'sha256').hexdigest()
    if expected:=entry.get('expected_lfs_sha256'):
        assert sha256==expected,(name,sha256,expected)
    else:
        digest=hashlib.sha1(b'blob '+str(size).encode()+b'\0')
        with path.open('rb') as f:
            while block:=f.read(1024*1024): digest.update(block)
        assert digest.hexdigest()==entry['git_blob_oid'],(name,digest.hexdigest())
    records.append({'file':name,'url':url,'size':size,'sha256':sha256,'integrity_verified':True,'elapsed_seconds':round(time.time()-start,2)})
    print(f'Verified {name}: {sha256}',flush=True)
(evidence/'files.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
(evidence/'model-files.sha256').write_text(''.join(f'{r["sha256"]}  {r["file"]}\n' for r in records),encoding='utf-8')
lock['downloaded_weights']=True
lock['local_weight_sha256']=next(r['sha256'] for r in records if r['file']=='llm.mnn.weight')
lock['all_files_verified']=True
lock_path.write_text(json.dumps(lock,ensure_ascii=False,indent=2),encoding='utf-8')
config=json.loads((destination/'config.json').read_text(encoding='utf-8'))
config.update(backend_type='cpu',thread_num=4,precision='low',memory='low',
              max_new_tokens=64,sampler_type='greedy',reuse_kv=False)
config['async']=False
(destination/'config.cpu.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
(evidence/'config.cpu.sha256').write_text(hashlib.sha256((destination/'config.cpu.json').read_bytes()).hexdigest()+'  config.cpu.json\n')
print('Model download and integrity checks completed. Inference has not been executed by this script.',flush=True)
