from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
out=R/'evidence/prior-stage-hashes.json';assert not out.exists()
hashes={}
for folder in ['gate0','mobile-llm-runtime-lab','gate2-decode','gate2b-decode-hotspots']:
    for p in (R.parent/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            with p.open('rb') as f:hashes[str(p.relative_to(R.parent))]=hashlib.file_digest(f,'sha256').hexdigest()
out.write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf-8')
p=(R.parent/'gate0/build_android_cpu.sh').read_text()
p=p.replace('# Gate 0 only. No source patching, package installation, model download, or ADB.', '# Gate2-C: clean pinned OpenCL build, no source edits.')
p=p.replace('build-android-arm64-cpu-gate0','build-android-arm64-opencl-gate2c')
p=p.replace('-DMNN_OPENCL=OFF','-DMNN_OPENCL=ON -DMNN_OPENCL_SIZE_CUT=OFF -DMNN_GPU_TIME_PROFILE=OFF')
(R/'scripts/build_opencl.sh').write_text(p,newline='\n')
(R/'scripts/build_opencl_profile.sh').write_text(p.replace('-DMNN_GPU_TIME_PROFILE=OFF','-DMNN_GPU_TIME_PROFILE=ON').replace('-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_FLAGS=-DOPENCL_FALLBACK_LOG -DCMAKE_BUILD_TYPE=Release'),newline='\n')
print('Prior-stage hashes:',len(hashes))
