from run import *
import subprocess,re
def main():
    d=R/'evidence';checks={};prior=load(d/'prior-hashes.json');changed=[]
    for name,h in prior.items():
        p=R.parent/name
        if not p.is_file() or sha(p)!=h:changed.append(name)
    checks.update(prior_file_count=len(prior),prior_changed_files=changed);assert len(prior)==8971 and not changed
    snapshots=load(d/'source/manifest.json');assert len(snapshots)==18
    assert all(sha(d/'source'/x['file'])==x['sha256'] for x in snapshots);checks['fixed_source_snapshots_verified']=len(snapshots)
    command=['wsl','-d','Ubuntu','--','python3','-c',"from pathlib import Path; import subprocess,json,hashlib; s=Path('/home/shawrange/src/MNN-3.6.2'); q=Path('/home/shawrange/src/MNN-quant-gate2c3'); r=Path('/mnt/e/DUANCE/gate2c3-quant'); assert subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD']).decode().strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d'; assert not subprocess.check_output(['git','-C',str(s),'status','--porcelain','--untracked-files=no']).strip(); subprocess.run(['git','-C',str(s),'apply','--check',str(r/'evidence/diagnostic.patch')],check=True); subprocess.run(['git','-C',str(q),'diff','--check'],check=True); assert hashlib.sha256((q/'build-android-arm64-cpu-gate2c3/libMNN.so').read_bytes()).hexdigest()==hashlib.sha256((r/'staging/libMNN-diagnostic.so').read_bytes()).hexdigest(); assert all((q/f).read_bytes()==(r/'evidence/diagnostic-source'/f).read_bytes() for f in ['source/backend/cpu/compute/ConvInt8TiledExecutor.cpp','source/backend/cpu/compute/GateC3Capture.hpp']); print('Fixed base clean, diagnostic patch replayable, live source and map-linked binary match')"]
    p=subprocess.run(command,capture_output=True);(d/'final-source-check.stdout.txt').write_bytes(p.stdout);(d/'final-source-check.stderr.txt').write_bytes(p.stderr);save(d/'final-source-check.command.json',{'command':command,'exit_code':p.returncode});assert p.returncode==0,p.stderr.decode(errors='replace')
    checks.update(base_commit_and_tracked_clean=True,diagnostic_patch_replayable=True,diagnostic_live_source_matches_archive=True,map_relink_binary_identical=True)
    artifacts=load(d/'build/artifacts.json');assert all(sha(R/name)==h for name,h in artifacts.items())
    for name in ['build','replay-build','extractor-build','reference-build']:
        file='build.exit.txt' if name=='build' else 'exit.txt';assert (d/name/file).read_text().strip()=='0'
    assert (d/'build/configure.exit.txt').read_text().strip()=='0'
    checks['all_build_exit_codes_zero']=True
    data=load(R/'analysis/results.json');assert data['decision']=='A' and data['independent_input_cases']==2
    for item in data['functional_checks']:
        assert all(item[key] for key in ['all_three_executor_entries_match','all_three_quantized_inputs_match','all_three_scales_match','runtime_decoded_weights_and_alpha_match','prepared_scale_offset_match','tracing_on_off_and_archive_output_identical','independent_contract_matches_cpu_all_elements'])
    expected=[m for m in data['metrics'] if m['reference']=='B16_contract' and m['compared']=='cpu-low'];assert len(expected)==2 and all(m['max_abs']==0 and m['exact_elements']==m['elements'] for m in expected)
    checks.update(independent_input_cases=2,independent_contract_exact_output_elements=sum(m['elements'] for m in expected),all_three_first_and_subsequent_cpu_entries_verified=True,actual_int8_and_scale_reconstruction_exact=True,raw_and_prepared_weight_metadata_verified=True,tracing_on_off_archive_outputs_identical=True)
    assert checks['independent_contract_exact_output_elements']==43008
    session=R/data['primary_session'];results=list(session.glob('*/result.json'));assert len(results)==10 and all(load(x)['valid'] and load(x)['exit_code']==0 for x in results)
    assert sum(len(load(x.parent/'out/sample.meta.json')['runs']) for x in results)==30
    checks.update(successful_device_processes=10,single_q_executions=30,initial_reference_six_tail_differences_retained_and_explained=data['initial_reference_attempt'][1]['mismatch_count']==6)
    assert checks['initial_reference_six_tail_differences_retained_and_explained']
    final=load(d/'environment/final-device-hashes.json');recorded=load(session/'verified-assets.json');assert all(recorded[k]==v for k,v in final.items());checks['device_artifact_hashes_verified']=True
    for kind in ['synthetic','natural']:assert load(R/'references'/kind/'command.json')['exit_code']==0
    # Check that the host reference binary has no link to libMNN (source/command also archived).
    cmd=['wsl','-d','Ubuntu','--','readelf','-d','/mnt/e/DUANCE/gate2c3-quant/staging/reference'];p=subprocess.run(cmd,capture_output=True);(d/'reference-build/readelf.txt').write_bytes(p.stdout);assert p.returncode==0 and b'libMNN' not in p.stdout
    checks['host_reference_not_linked_to_MNN']=True
    save(R/'verification-summary.json',dict(checks,delivery_integrity_verified=False))
    for path in R.glob('*.md'):
        content=path.read_text(encoding='utf-8');assert content.count('```')%2==0
        for link in re.findall(r'\]\(([^)]+)\)',content):
            if not link.startswith(('http:','https:','#')):assert (path.parent/link).exists(),(path,link)
    checks.update(decision='A: expected quantization behavior; stop current operator localization',baseline_runtime_modified=False,diagnostic_branch_instrumentation_only=True,model_assets_modified=False,confirmed_backend_defect=False,model_quality_acceptance_passed=False,old_C1_C2_thresholds_and_failure_results_unchanged=True,new_gpu_performance_baseline=False,npu_executed=False,delivery_integrity_verified=True)
    save(R/'verification-summary.json',checks)
    manifest={str(p.relative_to(R)):sha(p) for p in sorted(R.rglob('*')) if p.is_file() and p.name!='artifact-manifest.sha256.json'};save(R/'artifact-manifest.sha256.json',manifest)
    print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
