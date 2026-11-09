from pathlib import Path
p=Path('gate0/build_android_cpu.sh').read_text()
start=p.index('if [[ -n '); end=p.index('if [[ -e ', start)
p=p[:start]+p[end:]
p=p.replace('# Gate 0 only. No source patching, package installation, model download, or ADB.', '# Gate 2 diagnostic branch only; pinned source plus archived diagnostic.patch.')
p=p.replace('-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_FLAGS=-DMNN_GATE2_TRACE -DCMAKE_BUILD_TYPE=Release')
p=p.replace('printf \'Build artifacts produced;', 'printf \'Diagnostic artifacts produced;')
Path('gate2-decode/scripts/build_diagnostic.sh').write_text(p,newline='\n')
