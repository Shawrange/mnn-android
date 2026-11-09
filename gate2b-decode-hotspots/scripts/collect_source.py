from pathlib import Path
import subprocess,json,hashlib
R=Path('/mnt/e/DUANCE/gate2b-decode-hotspots');S=Path('/home/shawrange/src/MNN-3.6.2')
files=['transformers/llm/engine/tools/llm_bench.cpp','transformers/llm/engine/src/llm.cpp','transformers/llm/engine/src/speculative_decoding/generate.cpp','tools/cpp/Profiler.cpp','source/core/Pipeline.cpp','source/core/Session.cpp','source/core/TensorUtils.hpp','source/core/Backend.hpp','source/backend/cpu/CPUBackend.cpp','source/backend/cpu/CPUBackend.hpp','source/backend/arm82/Arm82Backend.cpp','source/backend/arm82/Arm82Functions.cpp','source/backend/cpu/compute/ConvolutionFloatFactory.cpp','source/backend/cpu/compute/ConvInt8TiledExecutor.cpp','source/backend/cpu/compute/ConvInt8TiledExecutor.hpp','source/backend/cpu/compute/DenseConvolutionTiledExecutor.cpp','source/backend/cpu/compute/Int8FunctionsOpt.cpp','source/backend/cpu/CPULayerNorm.cpp','source/backend/cpu/CPURaster.cpp','source/backend/cpu/CPUBinary.cpp','source/backend/cpu/CPUUnary.cpp','source/backend/cpu/CPUAttention.cpp','express/module/StaticModule.cpp','source/backend/cpu/ThreadPool.cpp','source/core/Concurrency.h','transformers/llm/export/utils/model.py','transformers/llm/export/utils/transformers.py']
files+=['source/backend/cpu/CPUConvolution.cpp','source/backend/cpu/CPUCast.cpp','source/backend/cpu/compute/CommonOptFunction.h','source/backend/cpu/compute/CPUExtension.hpp']
items=[]
for name in files:
    if not (S/name).is_file():continue
    raw=(S/name).read_bytes();blob=subprocess.check_output(['git','-C',str(S),'show','7e3c6fb5225d3ccf22807ee641332669df34650d:'+name]);assert raw==blob
    p=R/'evidence/source'/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(raw)
    items.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
(R/'evidence/source/manifest.json').write_text(json.dumps(items,indent=2))
print('Source snapshots:',len(items))
