from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

stages={}
for path in sorted((ROOT/'evidence/runtime').glob('*/stage-status.json')):
    status=read_json(path)
    if status['stage_completed']:
        stages[status['mode']]=path.parent
assert set(stages)=={'deploy','help','demo','bench'}
for stage,directory in stages.items():
    commands=read_json(directory/'commands.json')
    assert all(command['exit_code']==0 for command in commands),stage

demo_dir=stages['demo']
demo_raw=(demo_dir/'llm-demo.stdout.txt').read_bytes().decode('utf-8')
answer='北京是中国的首都，拥有丰富的文化和历史，是重要的国际城市。'
assert answer in demo_raw
assert re.search(r'prompt tokens num\s*=\s*18',demo_raw)
assert re.search(r'decode tokens num\s*=\s*16',demo_raw)
assert (demo_dir/'llm-demo.stderr.txt').stat().st_size==0
bench_dir=stages['bench']
bench=read_json(bench_dir/'bench-smoke.json')
assert bench['backend']=='CPU' and bench['threads']==4 and bench['precision']==2
assert len(bench['results'])==1
result=bench['results'][0]
assert result['type']=='prefill_and_decode' and result['prompt_len']==128 and result['generate_len']==64
assert result['prefill_tps']>0 and result['decode_tps']>0
assert (bench_dir/'llm-bench-smoke.stderr.txt').stat().st_size==0
inspection=read_json(ROOT/'evidence/build/inspection-summary.json')
assert inspection['configure_exit']==inspection['build_exit']==0
assert inspection['tracked_source_unchanged']
assert (ROOT/'evidence/build/final-tracked-status.txt').stat().st_size==0
assert (ROOT/'evidence/source-checkout/commit.txt').read_text().strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d'
assert int((ROOT/'evidence/installation/ndk-install.exit.txt').read_text())==0
assert int((ROOT/'evidence/model-download.exit.txt').read_text(encoding='utf-8-sig'))==0
model_lock=read_json(ROOT/'evidence/model/model-lock.json')
assert model_lock['downloaded_weights'] and model_lock['all_files_verified']
deployment=read_json(stages['deploy']/'deployment-hashes.json')
assert len(deployment)==10 and all(row['host_device_match'] for row in deployment)

summary=read_json(ROOT/'evidence/verification-summary.json')
summary.update({
    'ndk_installed':True,'ndk_version':'27.2.12479018','full_source_checkout_verified':True,
    'mnn_commit':'7e3c6fb5225d3ccf22807ee641332669df34650d',
    'android_configure_executed':True,'android_configure_exit':0,
    'android_build_executed':True,'android_build_exit':0,'elf_and_build_flags_verified':True,
    'weights_downloaded':True,'model_integrity_verified':True,'deployment_hashes_verified':True,
    'llm_demo_executed':True,'llm_demo_exit':0,'llm_demo_text_review_passed':True,
    'llm_bench_help_executed':True,'llm_bench_help_exit':0,
    'llm_bench_smoke_executed':True,'llm_bench_smoke_exit':0,'llm_bench_smoke_passed':True,
    'gate0_passed':True,'gate1_started':False,'runtime_core_modified':False,
    'reviewed_generated_text':answer,'demo_prompt_tokens':18,'demo_generated_tokens':16,
    'benchmark_measured_samples':1,'benchmark_warmup_runs':1,
    'benchmark_claim_scope':'Single CPU smoke only; no baseline stability or optimization claim.',
    'model_export_args':None,'model_exporter_commit':None,
    'runtime_evidence':{name:str(path.relative_to(ROOT)) for name,path in stages.items()},
    'remote_directory':(ROOT/'evidence/runtime/remote-path.txt').read_text().strip(),
    'finalized_at_utc':datetime.now(timezone.utc).isoformat(),
})
(ROOT/'evidence/verification-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

manifest=[]
for path in sorted((ROOT/'evidence').rglob('*')):
    if not path.is_file() or path.name=='evidence-files.sha256':continue
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest.append(f'{digest}  {path.relative_to(ROOT).as_posix()}\n')
for path in sorted(ROOT.iterdir()):
    if path.is_file() and path.suffix in {'.sh','.py','.md'}:
        manifest.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n')
(ROOT/'evidence/evidence-files.sha256').write_text(''.join(manifest),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
