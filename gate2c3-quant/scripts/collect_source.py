from pathlib import Path
import subprocess,json,hashlib
R=Path('/mnt/e/DUANCE/gate2c3-quant');S=Path('/home/shawrange/src/MNN-3.6.2');D=Path('/home/shawrange/src/MNN-quant-gate2c3');COMMIT='7e3c6fb5225d3ccf22807ee641332669df34650d'
files=['source/backend/cpu/compute/ConvInt8TiledExecutor.cpp','source/backend/cpu/compute/ConvInt8TiledExecutor.hpp','source/backend/cpu/compute/ConvolutionFloatFactory.cpp','source/backend/cpu/compute/Int8FunctionsOpt.cpp','source/backend/cpu/compute/Int8FunctionsOpt.h','source/backend/cpu/compute/CommonOptFunction.h','source/backend/cpu/CPUBackend.cpp','source/backend/arm82/Arm82Functions.cpp','source/backend/arm82/asm/arm64/low_memory/MNNQuantScaleFP16.S','source/backend/arm82/asm/arm64/low_memory/MNNDynamicQuantFP16_Pack8.S','source/backend/arm82/asm/arm64/low_memory/MNNAbsMaxFP16_pack8.S','source/backend/arm82/asm/arm64/low_memory/MNNGemmInt8AddBiasScale_ARMV86_w4_Unit_FP16.S','source/backend/cpu/arm/arm64/MNNPackC4Int8ForMatMulA_ARM86.S','source/core/ConvolutionCommon.cpp','source/core/ConvolutionCommon.hpp','source/core/Tensor.cpp','include/MNN/Interpreter.hpp','source/core/Schedule.cpp']
items=[]
for name in files:
    raw=(S/name).read_bytes();assert raw==subprocess.check_output(['git','-C',str(S),'show',COMMIT+':'+name])
    p=R/'evidence/source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);items.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest()})
(R/'evidence/source/manifest.json').write_text(json.dumps(items,indent=2))
for name in ['source/backend/cpu/compute/ConvInt8TiledExecutor.cpp','source/backend/cpu/compute/GateC3Capture.hpp']:
    p=R/'evidence/diagnostic-source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((D/name).read_bytes())
state={key:subprocess.check_output(['git','-C',str(path),*args]).decode() for key,path,args in [('base_head',S,['rev-parse','HEAD']),('base_status',S,['status','--porcelain','--untracked-files=no']),('diagnostic_branch',D,['branch','--show-current']),('diagnostic_status',D,['status','--short'])]}
assert state['base_head'].strip()==COMMIT and state['base_status']==''
(R/'evidence/source-state.json').write_text(json.dumps(state,indent=2))
print('Saved',len(items),'fixed source files and diagnostic branch evidence')
