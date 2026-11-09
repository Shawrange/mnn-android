from pathlib import Path
import hashlib
import json
import time
import urllib.request

root = Path(__file__).resolve().parent
metadata = json.loads((root/'evidence/installation/ndk-download.json').read_text())
downloads = root/'downloads'
downloads.mkdir(exist_ok=True)
destination = downloads/'android-ndk-r27c-linux.zip'
partial = destination.with_suffix('.zip.part')
start = time.time()
if not destination.exists():
    digest = hashlib.sha1()
    total = 0
    threshold = 64 * 1024 * 1024
    with urllib.request.urlopen(metadata['url'], timeout=60) as response, partial.open('wb') as output:
        while block := response.read(1024 * 1024):
            output.write(block)
            digest.update(block)
            total += len(block)
            if total >= threshold:
                print(f'NDK downloaded {total}/{metadata["size"]} bytes', flush=True)
                threshold += 64 * 1024 * 1024
    assert total == metadata['size'], (total, metadata['size'])
    assert digest.hexdigest() == metadata['checksum'], digest.hexdigest()
    partial.replace(destination)
data_hash = hashlib.file_digest(destination.open('rb'), 'sha1').hexdigest()
assert data_hash == metadata['checksum']
record = dict(metadata, actual_size=destination.stat().st_size, actual_sha1=data_hash,
              actual_sha256=hashlib.file_digest(destination.open('rb'), 'sha256').hexdigest(),
              checksum_verified=True, elapsed_seconds=round(time.time()-start, 2))
(root/'evidence/installation/ndk-archive-verification.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record, indent=2), flush=True)
