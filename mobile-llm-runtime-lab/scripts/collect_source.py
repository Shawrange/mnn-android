from pathlib import Path
import hashlib,json

source=Path('/home/shawrange/src/MNN-3.6.2')
out=Path('/mnt/e/DUANCE/mobile-llm-runtime-lab/evidence/source')
out.mkdir(parents=True,exist_ok=True)
paths=['transformers/llm/engine/tools/llm_bench.cpp','transformers/llm/engine/src/llm.cpp',
       'transformers/llm/engine/src/speculative_decoding/generate.cpp',
       'transformers/llm/engine/include/llm/llm.hpp',
       'source/backend/cpu/CPUKVCacheManager.cpp','source/backend/cpu/CPUAttention.cpp',
       'include/MNN/AutoTime.hpp','source/core/AutoTime.cpp',
       'transformers/llm/engine/src/llmconfig.hpp']
records=[]
for name in paths:
    path=source/name
    if not path.is_file():continue
    data=path.read_bytes()
    target=out/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    records.append({'path':name,'sha256':hashlib.sha256(data).hexdigest()})
(out/'manifest.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
