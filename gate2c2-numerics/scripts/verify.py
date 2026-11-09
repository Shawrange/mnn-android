from run import *
import subprocess,re
def main():
    checks={};prior=load(R/'evidence/prior-hashes.json');changed=[]
    for name,h in prior.items():
        p=R.parent/name
        if not p.is_file() or sha(p)!=h:changed.append(name)
    checks.update(prior_file_count=len(prior),prior_changed_files=changed);assert not changed
    source=load(R/'evidence/source/manifest.json')
    assert all(sha(R/'evidence/source'/x['file'])==x['sha256'] for x in source)
    checks['fixed_source_snapshot_count']=len(source)
    proc=subprocess.run(['wsl','-d','Ubuntu','--','bash','-lc','cd /home/shawrange/src/MNN-3.6.2 && git rev-parse HEAD && git status --porcelain --untracked-files=no'],capture_output=True)
    evidence=R/'evidence';(evidence/'final-source-state.stdout.txt').write_bytes(proc.stdout);(evidence/'final-source-state.stderr.txt').write_bytes(proc.stderr)
    assert proc.returncode==0 and proc.stdout.decode().strip()==C['mnn_commit'];checks['fixed_commit_tracked_clean']=True
    runs=[]
    for p in (R/'results').glob('*/*/result.json'):
        rec=load(p)
        if 'mode' not in rec or not rec['valid']:continue
        runs.append(rec)
        assert (p.parent/'run.exit.txt').read_text().strip()=='0'
        ids=load(p.parent/'out/sample.ids.json')
        for i in [0,1]:
            meta=load(p.parent/f'out/sample.r{i}.meta.json')
            assert meta['shape']==[1,1,151936] and meta['type']=='float32' and meta['stats']['nonfinite']==0 and meta['read_twice_identical']
            assert meta['prompt_len']==meta['all_seq_len']==meta['kv_history']==len(ids) and meta['generated']==0
            assert (p.parent/f'out/sample.r{i}.logits.f32').stat().st_size==151936*4
            if rec['mode']=='checkpoints':
                assert len(meta['checkpoints'])==11
                for t in meta['checkpoints']:
                    assert t['copy_succeeded'] and t['wait_result']==0 and t['stats']['nonfinite']==0
                    assert t['host_format']=='NCHW' and t['host_type']=='float32'
                    assert t['backend_type']==(3 if rec['backend']=='opencl' else (13 if rec['precision']=='low' else 0))
                    assert (p.parent/f"out/sample.r{i}.{t['key']}.f32").stat().st_size==t['stats']['elements']*4
    checks['valid_llm_processes']=len(runs);assert len(runs)==22
    data=load(R/'analysis/metrics.json');comparisons=data['comparisons']
    within=[m for m in comparisons if m['label']=='within_process'];cross=[m for m in comparisons if m['label']=='cross_process']
    assert len(within)==132 and all(m['identical_bytes'] for m in within)
    assert len(cross)==4 and all(m['identical_bytes'] for m in cross)
    logit=[m for m in comparisons if m['label']=='CPU_vs_GPU'];assert len(logit)==4
    checks.update(within_process_tensor_pairs_identical=len(within),low_cross_process_logits_pairs_identical=len(cross),logits_exploratory_screening_passed=all(m['exploratory_passed'] for m in logit))
    assert not checks['logits_exploratory_screening_passed']
    cp=[m for m in comparisons if m['label']=='checkpoint_CPU_vs_GPU'];assert len(cp)==44 and all(m['all_finite'] for m in cp)
    lowinput=[m for m in cp if m['precision']=='low' and m['checkpoint'] in ['embedding_on_backend','_input_layernorm_Mul_1_output_0','q_input']]
    assert len(lowinput)==6 and all(m['identical_bytes'] for m in lowinput);checks['low_first_projection_inputs_identical']=True
    replay=load(R/'analysis/replay.json');assert replay['valid_processes']==10 and len(replay['failed_processes'])==2 and len(replay['excluded_processes'])==20
    for m in replay['comparisons']:
        assert m['all_finite']
        if m['label'] in ['input_roundtrip','repeat_0_1','repeat_1_2','replay_vs_full']:assert m['identical_bytes']
    primary=R/replay['primary_session']
    for p in primary.glob('*/result.json'):
        actual=load(p.parent/'input-source.json');raw=(R/actual['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==actual['sha256']
        for i in [1,2]:assert (p.parent/f'out/sample.r{i}.conv_input.f32').read_bytes()==raw
        meta=load(p.parent/'out/sample.meta.json')
        for row in meta['runs']:
            assert row['exit_code']==row['wait']==0 and sum(x['type']=='Convolution' for x in row['ops'])==1
            assert all(x['type'] in ['Convolution','Raster'] for x in row['ops'])
    checks.update(valid_same_input_replay_processes=10,failed_replay_processes_retained=2,earlier_replay_processes_explicitly_excluded=20,measured_replay_entry_verified=True,warmup_callback_input_issue_recorded=len(replay['warmup_before_callback_input_mismatches'])==4)
    assert checks['warmup_callback_input_issue_recorded']
    versions=load(R/'evidence/environment/device-artifacts.json');assert len(versions)==9
    for v in versions:
        d=R/'results'/v['session']/'executable-evidence';tool='replay' if v['session'].startswith('replay') else 'numeric_probe'
        for b in ['cpu','opencl']:
            assert v['hashes'][v['remote']+'/'+b+'/'+tool]==sha(d/tool)
    checks['device_library_and_historical_executable_hash_records']=len(versions)
    for name in ['probe-build','replay-build']:assert (R/'evidence'/name/'exit.txt').read_text().strip()=='0'
    save(R/'verification-summary.json',dict(checks,delivery_integrity_verified=False))
    # Validate every portable Markdown link resolves; line references are in the surrounding prose.
    for p in R.glob('*.md'):
        content=p.read_text(encoding='utf-8');assert content.count('```')%2==0
        for link in re.findall(r'\]\(([^)]+)\)',content):
            if not link.startswith(('https:','http:','#')):assert (p.parent/link).exists(),(p,link)
    checks.update(runtime_source_modified=False,model_graph_or_weights_modified=False,npu_executed=False,performance_baseline_created=False,confirmed_backend_defect=False,decision='C: earliest significant difference localized to quantized projection compute paths; no patch justified',delivery_integrity_verified=True)
    save(R/'verification-summary.json',checks)
    manifest={}
    for p in sorted(R.rglob('*')):
        if p.is_file() and p.name!='artifact-manifest.sha256.json':manifest[str(p.relative_to(R))]=sha(p)
    save(R/'artifact-manifest.sha256.json',manifest)
    print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
