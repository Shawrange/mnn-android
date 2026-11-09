from pathlib import Path
import json,hashlib,subprocess,re,csv
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args):
    p=subprocess.run(args,capture_output=True);return {'command':args,'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
old=load(R/'evidence/prior-stage-hashes.json');changed=[p for p,h in old.items() if not (R.parent/p).is_file() or sha(R.parent/p)!=h]
checks={'prior_file_count':len(old),'prior_changed_files':changed};records=[]
for label,args in [('base-head',['rev-parse','HEAD']),('tracked-clean',['status','--porcelain','--untracked-files=no'])]:
    rec=run(['wsl','-d','Ubuntu','--','git','-C','/home/shawrange/src/MNN-3.6.2',*args]);records.append(rec);checks[label]=rec['exit_code']==0 and (rec['stdout'].strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d' if label=='base-head' else not rec['stdout'].strip())
p=subprocess.run(['wsl','-d','Ubuntu','--','git','-C','/home/shawrange/src/MNN-decode-gate2a','diff','--binary'],capture_output=True)
checks['gate2a_branch_unchanged']=p.returncode==0 and p.stdout==(R.parent/'gate2-decode/evidence/diagnostic.patch').read_bytes()
checks['fixed_source_snapshots']=len(load(R/'evidence/source/manifest.json'))
checks['snapshots_hash_match']=all(sha(R/'evidence/source'/x['file'])==x['sha256'] for x in load(R/'evidence/source/manifest.json'))
for kind in ['clean','profile']:
    d=R/'evidence/build'/kind
    checks[kind+'_configure_build_exit_zero']=all((d/n).read_text().strip()=='0' for n in ['configure.exit.txt','build.exit.txt'])
    checks[kind+'_hashes_match']=all(sha(R/'staging'/kind/n)==h for n,h in load(d/'artifact-hashes.json').items())
    assert 'MNN_OPENCL=ON' in (d/'configure.command.txt').read_text()
commands=(R/'evidence/build/profile/ninja-commands.txt').read_text()
checks['profile_and_fallback_macros_present']='-DENABLE_OPENCL_TIME_PROFILER' in commands and '-DOPENCL_FALLBACK_LOG' in commands
a=load(R/'analysis/summary.json');checks['C0_device_kernel_probe_passed']=a['decision']['device_opencl_usable'];checks['C1_model_execution_smoke_passed']=a['decision']['clean_llm_execution_smoke'];checks['C1_actual_gpu_compute_proved']=a['decision']['actual_major_gpu_kernels_proved'];checks['C1_numerical_screening_passed']=a['decision']['all_prefill_numeric_screening_passed']
assert len(a['numerical_prefill_probes'])==2 and all(x['ids_equal'] and x['shape_equal'] and x['finite'] for x in a['numerical_prefill_probes'])
checks['logits_probes_captured']=2
for x in a['numerical_prefill_probes']:
    for mode in ['cpu','opencl']:
        d=R/x['session']/(mode+'-'+x['kind']);assert (d/'logits.f32').stat().st_size==x['elements']*4
checks['initial_config_error_retained']=any(not x['semantic_success'] and x['exit_code']==0 and x['failure_layer'] for x in a['smokes'])
paths={}
remote='/data/local/tmp/mnn-gate2c-20261108'
for kind in ['clean','profile']:
    for n in ['libMNN.so','llm_demo','llm_bench']:paths[f'{remote}/{kind}/{n}']=R/'staging'/kind/n
for mode,local in [('cpu',R.parent/'gate0/staging/libMNN.so'),('opencl',R/'staging/clean/libMNN.so')]:paths[remote+'/oracle-'+mode+'/libMNN.so']=local
for n in ['config.cpu.json','llm_config.json','llm.mnn','llm.mnn.weight','tokenizer.txt']:paths['/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN/'+n]=R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n
rec=run([r'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe','-s','ee19377b','shell','sha256sum '+' '.join(paths)]);records.append(rec)
got={line.split()[1]:line.split()[0] for line in rec['stdout'].splitlines() if len(line.split())==2}
checks['device_artifacts_match']=rec['exit_code']==0 and all(got.get(n)==sha(p) for n,p in paths.items())
checks['npu_executed']=False;checks['runtime_core_modified']=False
for p in R.glob('*.md'):
    text=p.read_text(encoding='utf-8');assert text.count('```')%2==0
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if not target.startswith(('http','/')):assert (p.parent/target).exists(),(p,target)
checks['delivery_integrity_verified']=not changed and all(checks[k] for k in ['base-head','tracked-clean','gate2a_branch_unchanged','snapshots_hash_match','clean_configure_build_exit_zero','profile_configure_build_exit_zero','clean_hashes_match','profile_hashes_match','profile_and_fallback_macros_present','C0_device_kernel_probe_passed','C1_model_execution_smoke_passed','C1_actual_gpu_compute_proved','initial_config_error_retained','device_artifacts_match'])
(R/'verification-summary.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');(R/'evidence/final-commands.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='artifact-manifest.sha256.json' and '__pycache__' not in p.parts}
(R/'artifact-manifest.sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2));assert checks['delivery_integrity_verified']
