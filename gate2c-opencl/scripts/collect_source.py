from pathlib import Path
import subprocess,json,hashlib
R=Path('/mnt/e/DUANCE/gate2c-opencl');S=Path('/home/shawrange/src/MNN-3.6.2')
files=['CMakeLists.txt','project/android/build_64.sh','include/MNN/MNNForwardType.h','include/MNN/Interpreter.hpp','transformers/llm/engine/src/llm.cpp','transformers/llm/engine/src/llmconfig.hpp','transformers/llm/engine/include/llm/llm.hpp','transformers/llm/engine/tools/llm_bench.cpp','source/core/Schedule.cpp','source/core/Pipeline.cpp','source/core/Interpreter.cpp','source/core/Session.cpp','source/backend/opencl/CMakeLists.txt','source/backend/opencl/core/OpenCLBackend.cpp','source/backend/opencl/core/OpenCLBackend.hpp','source/backend/opencl/core/runtime/OpenCLRuntime.cpp','source/backend/opencl/core/runtime/OpenCLRuntime.hpp','source/backend/opencl/core/runtime/OpenCLWrapper.cpp','source/backend/opencl/core/runtime/OpenCLWrapper.hpp','source/backend/opencl/core/OpenCLRunningUtils.cpp','source/backend/opencl/execution/buffer/ConvBufLowMemoryExecution.cpp','source/backend/opencl/execution/buffer/AttentionBufExecution.cpp','source/backend/qnn/README.md','source/backend/qnn/CMakeLists.txt','source/backend/hexagon/README.md','source/backend/hexagon/CMakeLists.txt']
for name in ['qnn','hexagon']:
    files += [str(p.relative_to(S)) for p in (S/'source/backend'/name).glob('*') if p.is_file() and p.suffix in ['.cpp','.hpp'] and any(k in p.name.lower() for k in ['backend','runtime','interface','common'])]
files += ['docs/transformers/llm.md','docs/inference/npu.md','docs/tools/convert.md','source/core/ConvolutionCommon.cpp','source/backend/qnn/backend/QNNUtils.cpp','source/backend/hexagon/execution/HexagonConvolution.cpp','source/backend/hexagon/execution/HexagonAttention.cpp','source/backend/cpu/compute/ConvInt8TiledExecutor.cpp','source/backend/opencl/execution/image/CommonExecution.cpp']
for folder in ['source/backend/qnn/backend','source/backend/hexagon/backend']:
    files += [str(p.relative_to(S)) for p in (S/folder).glob('*') if p.suffix in ['.cpp','.hpp'] and any(x in p.name for x in ['Backend','Runtime','Wrapper','Interface'])]
items=[]
for name in dict.fromkeys(files):
    p=S/name
    if not p.is_file():continue
    raw=p.read_bytes();assert raw==subprocess.check_output(['git','-C',str(S),'show','7e3c6fb5225d3ccf22807ee641332669df34650d:'+name])
    d=R/'evidence/source'/name;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(raw);items.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
(R/'evidence/source/manifest.json').write_text(json.dumps(items,indent=2));print('Snapshots:',len(items))
