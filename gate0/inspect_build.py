from pathlib import Path
import hashlib,json,re

root=Path(__file__).resolve().parent
build=root/'evidence/build'
cache={}
for line in (build/'CMakeCache.txt').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith(('#','//')) and '=' in line:
        key,value=line.split('=',1)
        cache[key.split(':',1)[0]]=value
for key in ['MNN_BUILD_LLM','MNN_LOW_MEMORY','MNN_SUPPORT_TRANSFORMER_FUSE','MNN_ARM82']:
    assert cache[key]=='ON',(key,cache.get(key))
for key in ['MNN_OPENCL','MNN_OPENGL','MNN_VULKAN','MNN_CUDA','MNN_QNN','MNN_HEXAGON','MNN_NPU','MNN_NNAPI','MNN_SME2','MNN_SEP_BUILD','MNN_KLEIDIAI']:
    assert cache[key]=='OFF',(key,cache.get(key))
for key,value in {'CMAKE_GENERATOR':'Ninja','ANDROID_ABI':'arm64-v8a','ANDROID_STL':'c++_static','ANDROID_PLATFORM':'android-21'}.items():
    assert cache[key]==value,(key,cache.get(key))
records=[]
system_libraries={'libm.so','libdl.so','libc.so','liblog.so','libandroid.so'}
for name in ['llm_demo','llm_bench','libMNN.so']:
    elf=(build/f'{name}.readelf.txt').read_text(encoding='utf-8')
    assert 'ELF64' in elf and 'AArch64' in elf
    needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]',elf)
    assert set(needed)<=system_libraries|{'libMNN.so'},needed
    if name!='libMNN.so':
        assert 'libMNN.so' in needed and '/system/bin/linker64' in elf
        assert 'NOW PIE' in elf
    assert 'libc++_shared.so' not in needed
    load_lines=[line.strip() for line in elf.splitlines() if line.strip().startswith('LOAD ')]
    assert load_lines and all(line.endswith('0x4000') for line in load_lines)
    path=root/'staging'/name
    with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    records.append({'file':name,'size':path.stat().st_size,'sha256':digest,'class':'ELF64','machine':'AArch64','needed':needed,'load_alignment':'0x4000','android_interpreter':'/system/bin/linker64' if name!='libMNN.so' else None})
keys=['CMAKE_GENERATOR','CMAKE_BUILD_TYPE','CMAKE_CXX_STANDARD','CMAKE_CXX_COMPILER','CMAKE_TOOLCHAIN_FILE','ANDROID_ABI','ANDROID_PLATFORM','ANDROID_STL','MNN_BUILD_LLM','MNN_LOW_MEMORY','MNN_SUPPORT_TRANSFORMER_FUSE','MNN_ARM82','MNN_SME2','MNN_SEP_BUILD','MNN_OPENCL','MNN_VULKAN','MNN_CUDA','MNN_QNN','MNN_HEXAGON','MNN_WITH_PLUGIN']
compiler_info=(build/'CMakeCXXCompiler.cmake').read_text(encoding='utf-8')
cache['CMAKE_CXX_COMPILER']=re.search(r'set\(CMAKE_CXX_COMPILER "([^"]+)"\)',compiler_info).group(1)
summary={'configure_exit':int((build/'configure.exit.txt').read_text()),'build_exit':int((build/'build.exit.txt').read_text()),'tracked_source_unchanged':(build/'final-tracked-status.txt').stat().st_size==0,'flags':{k:cache.get(k) for k in keys},'artifacts':records}
assert summary['configure_exit']==summary['build_exit']==0
(build/'inspection-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
