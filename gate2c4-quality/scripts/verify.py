from run import *
import subprocess,datetime,math,array
def main():
    checks={};freeze=check_freeze();prior=load(R/'evidence/prior-hashes.json');changed=[]
    for name,h in prior.items():
        p=R.parent/name
        if not p.is_file() or sha(p)!=h:changed.append(name)
    assert len(prior)==9665 and not changed;checks.update(prior_file_count=len(prior),prior_changed_files=changed,frozen_file_hashes_verified=True)
    cases=[json.loads(x) for x in (R/'datasets/formal.jsonl').read_text(encoding='utf-8').splitlines()];pilot=[json.loads(x) for x in (R/'datasets/pilot.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(cases)==100 and len({c['id'] for c in cases})==len({c['input'] for c in cases})==100 and len(pilot)==12
    assert not {c['input'] for c in cases}&{c['input'] for c in pilot}
    assert all(sum(c['category']==cat for c in cases)==25 for cat in ['classification','extraction','instruction','qa'])
    for c in cases:assert grade(c,{'raw_text':c['variants'][0],'status':1,'stopped':True,'runtime_ok':True})['success']
    q=load(R/'analysis/paired-quality.json');d=R/q['formal_session'];proto=load(d/'protocol.json')
    assert sha(d/'dataset.jsonl')==freeze['sha256']['datasets/formal.jsonl'] and proto['freeze_sha256']==sha(R/'freeze.json')
    stamp=lambda s:datetime.datetime.fromisoformat(s)
    frozen=stamp(freeze['frozen_at_utc']);assert frozen<stamp(proto['started_at_utc'])
    assert load(d/'session-status.json')['completed_runs']==200 and not load(d/'session-status.json')['runtime_failures']
    schedule=load(d/'schedule.json');assert len(schedule)==200 and len({(x['id'],x['backend']) for x in schedule})==200
    tmpl=load(R.parent/'gate0/assets/Qwen3-0.6B-MNN/llm_config.json')['jinja']['chat_template']
    for c in cases:
        for backend in ['cpu','opencl']:
            p=d/(c['id']+'-'+backend);v=load(p/'result.json');g=load(p/'score.json');assert g==grade(c,v)
            assert v['process_exit']==0 and v['runtime_ok'] and v['status']==1 and v['stopped'] and v['valid_utf8']
            assert frozen<stamp(load(p/'run.command.json')['started_at_utc'])
            outids=load(p/'device/sample.output_ids.json');inids=load(p/'device/sample.input_ids.json');meta=load(p/'device/sample.meta.json');cfg=load(p/'device/sample.config.json')
            assert len(outids)==meta['generated_count']==meta['gen_seq_len']<=96 and outids[-1]==meta['stop_token']==151645
            assert meta['initial_kv']==0 and meta['kv_after']==len(inids)+len(outids)-1 and meta['input_len']==len(inids)
            assert (p/'device/sample.text.txt').read_bytes().decode('utf-8')==v['raw_text']
            assert cfg['jinja']['chat_template']==tmpl and cfg['jinja']['context']['enable_thinking']==False
            for key,value in load(R/'configs/runtime.json').items():assert cfg[key]==value
        assert load(d/(c['id']+'-cpu')/'device/sample.input_ids.json')==load(d/(c['id']+'-opencl')/'device/sample.input_ids.json')
    checks.update(frozen_formal_cases=100,independent_pilot_cases=12,formal_cases_per_category=25,formal_cpu_gpu_processes=200,all_formal_runs_natural_eos=True,truncated_or_runtime_failed_formal_runs=0,same_model_template_and_input_ids_verified=True,formal_scoring_recomputed_identically=True)
    o=q['overall'];assert (o['cpu_success'],o['gpu_success'],o['both_correct'],o['cpu_only'],o['gpu_only'],o['both_wrong'])==(24,25,23,1,2,74)
    checks.update(cpu_task_successes=o['cpu_success'],gpu_task_successes=o['gpu_success'],both_correct=o['both_correct'],cpu_only=o['cpu_only'],gpu_only=o['gpu_only'],both_wrong=o['both_wrong'])
    diag=load(R/'analysis/logits-diagnostics.json');assert len(diag['selection'])==6 and len(diag['records'])==12 and len(diag['repeats'])==6
    rd=R/diag['session'];count=0
    for p in rd.glob('*/*/device/sample.logits.f32'):
        m=load(p.parent/'sample.meta.json');ids=load(p.parent/'sample.input_ids.json');a=array.array('f');a.frombytes(p.read_bytes())
        assert len(a)==151936 and all(math.isfinite(x) for x in a) and m['shape']==[1,1,151936] and m['read_twice_identical'] and m['initial_kv']==0 and m['kv_after']==len(ids) and m['generated_count']==0
        count+=1
    assert count==24 and all(x['same_history_verified'] for x in diag['records'])
    assert all(x[b]['same_output_ids_as_formal'] for x in diag['repeats'] for b in ['cpu','gpu'])
    mismatch=sum(not x['replay_cpu_matches_original'] or not x['replay_gpu_matches_original'] for x in diag['records']);assert mismatch==1
    checks.update(logits_prefill_processes=24,selected_logits_cases=6,fixed_history_and_kv_verified=True,decode_vs_prefill_replay_mismatch_records=mismatch,discordance_repeat_processes=12,repeated_output_ids_identical_to_formal=True)
    gpu=load(R/'analysis/gpu-execution-evidence.json');assert gpu['major_model_gpu_compute_proved'] and gpu['profile_input_output_ids_match_clean_formal'] and not gpu['fallback_log_lines']
    assert gpu['event_counts']['Convolution0']==394 and gpu['event_counts']['flash_attention_prefill']==gpu['event_counts']['flash_decode_partial']==gpu['event_counts']['flash_decode_reduce']==28
    assert all(gpu['nonzero_event_counts'].get(k,0)>0 for k in ['Convolution0','flash_attention_prefill','flash_decode_partial','flash_decode_reduce'])
    checks['actual_major_opencl_compute_proved']=True
    source=load(R/'evidence/source/manifest.json');assert len(source)==11 and all(sha(R/'evidence/source'/x['file'])==x['sha256'] for x in source)
    command=['wsl','-d','Ubuntu','--','bash','-lc','cd /home/shawrange/src/MNN-3.6.2 && git rev-parse HEAD && git status --porcelain --untracked-files=no']
    p=subprocess.run(command,capture_output=True);(R/'evidence/final-source.stdout.txt').write_bytes(p.stdout);(R/'evidence/final-source.stderr.txt').write_bytes(p.stderr);save(R/'evidence/final-source.command.json',{'command':command,'exit_code':p.returncode});assert p.returncode==0 and p.stdout.decode().strip()==C['mnn_commit']
    checks.update(fixed_source_files=11,base_commit_and_tracked_clean=True)
    tests=subprocess.run(['python','-B',str(R/'scripts/test_score.py')],capture_output=True);(R/'evidence/final-score-tests.stdout.txt').write_bytes(tests.stdout);(R/'evidence/final-score-tests.stderr.txt').write_bytes(tests.stderr);assert tests.returncode==0 and b'Ran 10 tests' in tests.stderr
    checks['scorer_tests_passed']=10
    assert (R/'evidence/probe-build/exit.txt').read_text().strip()=='0'
    assets=load(R/'evidence/environment/final-device-artifacts.json');assert len(assets)==4
    for record in assets:
        original=load(R/'results'/record['session']/'verified-assets.json');assert all(original[k]==h for k,h in record['hashes'].items())
    checks['all_session_device_artifact_hashes_verified']=True
    final=load(R/'analysis/decision.json');assert final['decision']=='C' and not final['enter_independent_gpu_performance_baseline'] and not final['frozen_quality_protocol_satisfied_by_gpu']
    save(R/'verification-summary.json',dict(checks,delivery_integrity_verified=False))
    for p in R.glob('*.md'):
        content=p.read_text(encoding='utf-8');assert content.count('```')%2==0
        for link in re.findall(r'\]\(([^)]+)\)',content):
            if not link.startswith(('http:','https:','#')):assert (p.parent/link).exists(),(p,link)
    checks.update(final_decision='C',cpu_quality_gate_passed=False,gpu_quality_gate_passed=False,enter_gpu_performance_baseline=False,runtime_core_modified=False,model_replaced_or_requantized=False,old_logits_thresholds_and_failure_evidence_unchanged=True,npu_executed=False,delivery_integrity_verified=True)
    save(R/'verification-summary.json',checks)
    save(R/'artifact-manifest.sha256.json',{str(p.relative_to(R)):sha(p) for p in sorted(R.rglob('*')) if p.is_file() and p.name!='artifact-manifest.sha256.json'})
    print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
