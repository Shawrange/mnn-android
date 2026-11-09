from pathlib import Path
import hashlib,json,subprocess,sys,csv
R=Path(__file__).resolve().parents[1];L=R.parent/'mobile-llm-runtime-lab';G=R.parent/'gate0'
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args):
    p=subprocess.run(args,capture_output=True);return {'command':args,'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
checks={};records=[]
old=json.loads((R/'evidence/gate1-audit/gate1-preservation-hashes.json').read_text())
changed=[n for n,h in old.items() if not (L/n).is_file() or digest(L/n)!=h]
checks['gate1_original_files_checked']=len(old);checks['gate1_changed_files']=changed
expected={'llm_demo':'37e65f0a8881699ec22bc96dd3ec2457c00ec3699ff2e4a7ef810ca8b1b915d9','llm_bench':'fd85bf65a75656d023feb9e2ad315f6ee7c6033c8f1591a835e54d2985db4676','libMNN.so':'47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e'}
checks['clean_binaries_unchanged']=all(digest(G/'staging'/n)==h for n,h in expected.items())
for label,args in [('clean-head',['git','-C','/home/shawrange/src/MNN-3.6.2','rev-parse','HEAD']),('clean-status',['git','-C','/home/shawrange/src/MNN-3.6.2','status','--porcelain','--untracked-files=no']),('patch-check',['git','-C','/home/shawrange/src/MNN-3.6.2','apply','--check','/mnt/e/DUANCE/gate2-decode/evidence/diagnostic.patch']),('diff-check',['git','-C','/home/shawrange/src/MNN-decode-gate2a','diff','--check'])]:
    rec=run(['wsl','-d','Ubuntu','--',*args]);rec['label']=label;records.append(rec);checks[label]=rec['exit_code']==0
    if label=='clean-head':checks[label] &= rec['stdout'].strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d'
    if label=='clean-status':checks[label] &= not rec['stdout'].strip()
rec=subprocess.run(['wsl','-d','Ubuntu','--','git','-C','/home/shawrange/src/MNN-decode-gate2a','diff','--binary'],capture_output=True)
checks['live_patch_matches_archive']=rec.returncode==0 and rec.stdout==(R/'evidence/diagnostic.patch').read_bytes()
adb=r'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe';remote='/data/local/tmp/mnn-gate0-20261108T134731469951Z'
paths={remote+'/'+n:G/'staging'/n for n in expected}
for p in (G/'assets/Qwen3-0.6B-MNN').iterdir():
    if p.name in ['config.cpu.json','llm_config.json','llm.mnn','llm.mnn.weight','tokenizer.txt']:paths[remote+'/Qwen3-0.6B-MNN/'+p.name]=p
for mode,local in [('clean',G/'staging'),('diag',R/'staging')]:
    for n in ['libMNN.so','llm_bench']:paths[remote+'/gate2a-diagnostic/'+mode+'/'+n]=local/n
paths[remote+'/gate2a-diagnostic/correctness']=R/'staging/correctness'
rec=run([adb,'-s','ee19377b','shell','sha256sum '+' '.join(paths)]);records.append(rec)
actual={line.split()[1]:line.split()[0] for line in rec['stdout'].splitlines() if len(line.split())==2}
checks['final_remote_assets_match']=rec['exit_code']==0 and all(actual.get(n)==digest(p) for n,p in paths.items())
checks['model_weight_sha256']=digest(G/'assets/Qwen3-0.6B-MNN/llm.mnn.weight')
checks['correctness_sessions_completed']=all(json.loads(p.read_text())['status']=='completed' for p in (R/'results').glob('correctness-*/session-status.json'))
samples=[json.loads(p.read_text()) for p in (R/'results').glob('control-*/*/sample.json')]
checks['control_samples']=len(samples);checks['all_control_samples_success']=len(samples)==36 and all(s['status']=='success' and s['exit_code']==0 for s in samples)
checks['control_sessions_completed']=all(json.loads(p.read_text())['status']=='completed' for p in (R/'results').glob('control-*/session-status.json'))
checks['trace_control_steps_including_warmup']=sum(int(s['trace_validation']['status']['steps']) for s in samples if s.get('trace_validation'))
checks['trace_control_growth_events_including_warmup']=sum(int(s['trace_validation']['status']['events']) for s in samples if s.get('trace_validation'))
checks['trace_control_dropped']=sum(int(s['trace_validation']['status']['dropped']) for s in samples if s.get('trace_validation'))
summary=json.loads((R/'analysis/summary.json').read_text())
checks['analysis_matches_samples']=summary['samples']==len(samples) and not summary['failed']
checks['independent_trace_validation']=json.loads((R/'evidence/independent-validation.json').read_text())['passed']
source_snapshots=json.loads((R/'evidence/source/snapshot-verification.json').read_text())
checks['source_snapshots_verified']=len(source_snapshots)
checks['source_snapshots_match_fixed_commit']=len(source_snapshots)==15 and all(x['matches_fixed_commit'] for x in source_snapshots)
checks['trace_native_difference_ms_max']=max(abs(t['trace_minus_native_ms']) for t in summary['trace_checks'])
checks['passed']=not changed and all(checks[k] for k in ['clean_binaries_unchanged','clean-head','clean-status','patch-check','diff-check','live_patch_matches_archive','final_remote_assets_match','correctness_sessions_completed','all_control_samples_success','control_sessions_completed','analysis_matches_samples','independent_trace_validation','source_snapshots_match_fixed_commit']) and checks['trace_control_dropped']==0
(R/'evidence/final-verification-commands.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
(R/'verification-summary.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False),encoding='utf-8')
manifest={str(p.relative_to(R)):digest(p) for p in R.rglob('*') if p.is_file() and p.name!='artifact-manifest.sha256.json' and '__pycache__' not in p.parts}
(R/'artifact-manifest.sha256.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(checks,indent=2,ensure_ascii=False))
sys.exit(0 if checks['passed'] else 1)
