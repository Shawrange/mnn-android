from pathlib import Path
import subprocess,json,hashlib
R=Path('/mnt/e/DUANCE/gate2c4-quality');S=Path('/home/shawrange/src/MNN-3.6.2');C='7e3c6fb5225d3ccf22807ee641332669df34650d'
files=['transformers/llm/engine/src/llm.cpp','transformers/llm/engine/src/llmconfig.hpp','transformers/llm/engine/include/llm/llm.hpp','transformers/llm/engine/src/tokenizer/tokenizer.cpp','transformers/llm/engine/src/tokenizer/tokenizer.hpp','transformers/llm/engine/src/speculative_decoding/generate.cpp','transformers/llm/engine/src/sampler.cpp','express/Expr.cpp','source/backend/opencl/core/runtime/OpenCLRuntime.cpp','source/backend/opencl/core/OpenCLBackend.cpp','include/MNN/MNNForwardType.h']
manifest=[]
for name in files:
    raw=(S/name).read_bytes();assert raw==subprocess.check_output(['git','-C',str(S),'show',C+':'+name]);p=R/'evidence/source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);manifest.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
(R/'evidence/source/manifest.json').write_text(json.dumps(manifest,indent=2))
state={'commit':subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD']).decode().strip(),'tracked_status':subprocess.check_output(['git','-C',str(S),'status','--porcelain','--untracked-files=no']).decode()};assert state['commit']==C and not state['tracked_status'];(R/'evidence/source-state.json').write_text(json.dumps(state,indent=2));print('Fixed snapshots',len(files))
