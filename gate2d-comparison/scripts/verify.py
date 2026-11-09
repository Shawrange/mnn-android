"""Offline evidence audit; does not launch inference or rewrite prior files."""
from run import *
from analyze import aggregate
import collections,datetime
def main():
    checks={};prior=load(R/'evidence/prior-hashes.json');changed=[n for n,h in prior.items() if not (R.parent/n).is_file() or sha(R.parent/n)!=h]
    assert not changed;checks.update(prior_file_count=len(prior),prior_changed_files=changed)
    frozen=load(R/'freeze.json')
    for n,h in frozen['sha256'].items():assert sha(R/n)==h,('Frozen file changed',n)
    checks['frozen_files_verified']=True
    start=load(R/'FORMAL_STARTED.json');d=R/start['session'];proto=load(d/'protocol.json');status=load(d/'session-status.json');schedule=load(d/'schedule.json')
    assert proto['freeze_sha256']==sha(R/'freeze.json') and schedule==load(R/'configs/schedule.json')
    dt=datetime.datetime.fromisoformat;assert dt(frozen['frozen_at_utc'])<dt(proto['started_at_utc'])
    assert len(schedule)==36 and all(n==6 for n in collections.Counter((x['backend'],x['pp'],x['tg']) for x in schedule).values())
    assert status['status']=='completed' and status['attempted']==status['successful']==36
    samples=[load(p) for p in sorted(d.glob('*/sample.json'))];assert len(samples)==36
    for i,s in enumerate(samples,1):
        expected=dict(schedule[i-1],index=i)
        for k,v in expected.items():assert s[k]==v
        assert s['status']=='success' and s['exit_code']==s['json_pull_exit_code']==0
        assert s['effective_dynamic_option']==0 and s['actual_length_directly_exported']==False
        sub=d/f'{i:03}-b{s["block"]:02}-{s["backend"]}-pp{s["pp"]}-tg{s["tg"]}'
        raw=load(sub/'benchmark.json');parsed=parse(raw,s['backend'],s['pp'],s['tg']);assert abs(raw['modelSize']-450810338/1024**3)<1e-9
        for k,value in parsed.items():assert s[k]==value
        cmd=load(sub/'benchmark.command.json');assert cmd['exit_code']==0 and '--profile' not in cmd['command'][-1] and './llm_bench' in cmd['command'][-1] and '-rep 1' in cmd['command'][-1]
        assert dt(cmd['started_at_utc'])>=dt(frozen['frozen_at_utc']) and s['max_rss_kib']>0
        for side in ['before','after']:assert s[side]['query_exit_code']==0 and s[side]['thermal_status']==0
        v=s['before'];assert v['skin_c']<=38 and v['battery_c']<=36 and v['cpu_max_c']<=80
        assert s['cooldown']['seconds']>=15
    for i in range(0,36,2):
        a,b=schedule[i:i+2];assert (a['block'],a['pp'],a['tg'])==(b['block'],b['pp'],b['tg']) and a['backend']!=b['backend']
    checks.update(formal_process_count=36,formal_successful=36,formal_failed=0,independent_processes_per_backend_workload=6,paired_groups=18,warmup_requests_per_process=1,measured_requests_per_process=1,source_constrained_formal_length=True,direct_formal_output_ids_available=False)
    func=R/frozen['functional_session']
    for b in ['cpu','opencl']:
        v=load(func/b/'count-contract.json');cfg=v['config']
        for k,value in {'backend_type':b,'precision':'low','memory':'low','power':'normal','ignore_eos':True,'async':False,'sampler_type':'greedy','reuse_kv':False,'dynamic_option':0,'attention_mode':8,'thread_num':4}.items():assert cfg[k]==value
        assert len(v['runs'])==6
        for x in v['runs']:assert x['gen_seq_len']==x['tg']==len(x['output_ids']) and x['kv_after']==x['pp']+x['tg'] and x['input_ids']==load(R/'configs'/f'input-{x["pp"]}.json')
    checks['functional_exact_count_and_kv_checks']=12
    archives={n.replace('\\','/'):h for n,h in load(R/'evidence/archived-artifact-hashes.json').items()}
    for n,h in archives.items():assert sha(R/n)==h
    assert archives['staging/cpu/libMNN.so']=='47b5db44b7acdaee876c733473ea9124cf71b645b6e53976d3bfd6ad313d120e'
    assert archives['staging/opencl/libMNN.so']=='4c66c06bbc083f3d123e62cdd6ec62a644e7a120d5a1509f297ffe856efa8f61'
    for b in ['cpu','opencl']:
        ninja=(R/f'evidence/build/{b}/build.ninja').read_text();assert '-DDUMP_PROFILE_INFO' not in ninja and '-DMNN_GATE2' not in ninja and '-DMNN_GATEC3' not in ninja and '-DOPENCL_FALLBACK_LOG' not in ninja and '-DMNN_GPU_TIME_PROFILE' not in ninja
        cache=(R/f'evidence/build/{b}/CMakeCache.txt').read_text();assert 'CMAKE_BUILD_TYPE:STRING=Release' in cache and 'MNN_GPU_TIME_PROFILE:BOOL=OFF' in cache
    source=load(R/'evidence/source-state.json');assert source['commit']==C['mnn_commit'] and not source['tracked_status']
    final=load(R/'evidence/final-source-state.json');assert final['commit']==C['mnn_commit'] and not final['tracked_status']
    for item in load(R/'evidence/source/manifest.json'):assert sha(R/'evidence/source'/item['file'])==item['sha256']
    q=load(R/'analysis/summary.json');assert q['attempted']==q['successful']==36 and not q['failed'] and len(q['pairs'])==18 and all(x['n']==6 for x in q['groups'])
    computed=aggregate(samples)
    for k in ['attempted','successful','groups','pairs','paired_summary']:assert q[k]==computed[k]
    final_device=load(R/'evidence/final-device-check/verified.json');assert final_device['all_original_assets_unchanged'] and final_device['sha256']==load(R/'deployment.json')['hashes']
    states=load(R/'analysis/device-state-summary.json');assert states['snapshots']==72 and states['gpu_sysfs_permission_denied_before_runs']==36
    checks.update(clean_archived_binaries_verified=True,no_formal_profiling_or_tracing=True,fixed_source_verified=True,raw_benchmark_json_and_analysis_verified=True,no_historical_cpu_pooling=True,request_e2e_measured=False,pss_measured=False,gpu_vram_measured=False,gpu_frequency_readable=False,npu_executed=False,runtime_core_changed=False,model_changed=False,extra_formal_runs_added=False)
    save(R/'verification-summary.json',checks);print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
