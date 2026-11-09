from pathlib import Path
import subprocess,json,hashlib
R=Path('/mnt/e/DUANCE/gate2c2-numerics');S=Path('/home/shawrange/src/MNN-3.6.2');COMMIT='7e3c6fb5225d3ccf22807ee641332669df34650d'
files=['transformers/llm/engine/src/llm.cpp','transformers/llm/engine/src/llmconfig.hpp','transformers/llm/engine/src/speculative_decoding/generate.cpp','transformers/llm/engine/include/llm/llm.hpp','include/MNN/expr/Expr.hpp','include/MNN/expr/Executor.hpp','include/MNN/Interpreter.hpp','include/MNN/MNNForwardType.h','include/MNN/Tensor.hpp','express/Expr.cpp','express/Executor.cpp','express/module/StaticModule.cpp','source/core/Tensor.cpp','source/core/TensorUtils.hpp','source/core/TensorUtils.cpp','source/core/Pipeline.cpp','source/core/Session.cpp','source/core/Backend.hpp','source/core/Schedule.cpp','source/core/Interpreter.cpp','source/backend/cpu/CPUBackend.cpp','source/backend/cpu/CPUBackend.hpp','source/backend/arm82/Arm82Backend.cpp','source/backend/cpu/compute/ConvolutionFloatFactory.cpp','source/backend/cpu/compute/ConvInt8TiledExecutor.cpp','source/backend/cpu/compute/DenseConvolutionTiledExecutor.cpp','source/backend/opencl/core/OpenCLBackend.cpp','source/backend/opencl/core/OpenCLBackend.hpp','source/backend/opencl/core/runtime/OpenCLRuntime.cpp','source/backend/opencl/execution/buffer/ConvBufLowMemoryExecution.cpp','source/backend/opencl/execution/cl/gemm_conv1x1_int4_b4_buf.cl','source/backend/opencl/execution/cl/gemm_conv1x1_int4_b8_buf.cl','source/backend/opencl/execution/cl/layernorm_buf.cl','source/backend/cpu/CPULayerNorm.cpp','source/core/ConvolutionCommon.cpp']
files+=['source/core/WrapExecution.cpp','source/backend/opencl/execution/cl/gemv_conv1x1_buf.cl','source/backend/opencl/execution/cl/gemm_conv1x1_layout_buf.cl']
items=[]
for name in files:
    p=S/name;raw=p.read_bytes();assert raw==subprocess.check_output(['git','-C',str(S),'show',COMMIT+':'+name])
    out=R/'evidence/source'/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(raw);items.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
(R/'evidence/source/manifest.json').write_text(json.dumps(items,indent=2))
meta={'head':subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD']).decode().strip(),'tracked_status':subprocess.check_output(['git','-C',str(S),'status','--porcelain','--untracked-files=no']).decode()}
assert meta['head']==COMMIT and meta['tracked_status']==''
(R/'evidence/source-state.json').write_text(json.dumps(meta,indent=2));print('Fixed snapshots',len(items))
