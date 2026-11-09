"""Offline device-state summary; snapshots are not in-run frequency telemetry."""
from analyze import stats
from run import *
import collections
def main():
    dep=load(R/'FORMAL_STARTED.json');d=R/dep['session'];samples=[load(p) for p in sorted(d.glob('*/sample.json'))];states=[];policies=collections.defaultdict(lambda:collections.defaultdict(list));groups=[]
    for s in samples:
        for side in ['before','after']:
            if side not in s:continue
            v=s[side];states.append(v)
            for p,values in v['policies'].items():
                for k in ['scaling_cur_freq','scaling_min_freq','scaling_max_freq','cpuinfo_max_freq']:
                    if values.get(k,'').isdigit():policies[p][k].append(int(values[k]))
    for b in ['cpu','opencl']:
        ss=[s for s in samples if s['backend']==b and s['status']=='success'];vv=[s[side] for s in ss for side in ['before','after']]
        groups.append({'backend':b,'processes':len(ss),'state_snapshots':len(vv),'state':{k:stats([v[k] for v in vv if v.get(k) is not None]) for k in ['skin_c','battery_c','cpu_max_c','mem_available_kib'] if any(v.get(k) is not None for v in vv)},'whole_process_context_switches':{k:stats([s[k] for s in ss if s.get(k) is not None]) for k in ['voluntary_context_switches','involuntary_context_switches'] if any(s.get(k) is not None for s in ss)}})
    gpu=[max(v['hal_temperatures_c'][k] for k in v['hal_temperatures_c'] if k.startswith('GPU')) for v in states if any(k.startswith('GPU') for k in v['hal_temperatures_c'])]
    denied=sum('Permission denied' in (p.parent/(p.stem.split('.')[0]+'.stderr.txt')).read_text(encoding='utf-8',errors='replace') for p in d.glob('*/before.stdout.txt'))
    result={'formal_session':str(d.relative_to(R)),'snapshots':len(states),'all_usb_powered':all(v['usb_powered'] for v in states),'battery_percent_range':[min(v['battery_percent'] for v in states),max(v['battery_percent'] for v in states)],'thermal_status_values':sorted({v['thermal_status'] for v in states}),
        'screen_states':sorted({x for v in states for x in v['screen_state']}),'overall':{k:stats([v[k] for v in states if v.get(k) is not None]) for k in ['skin_c','battery_c','cpu_max_c','mem_available_kib']},
        'gpu_hal_max_c':stats(gpu) if gpu else None,'cpu_policy_snapshots_khz':{p:{k:stats(vals) for k,vals in fields.items()} for p,fields in policies.items()},'by_backend':groups,
        'minimum_gap_seconds':15,'cooldown_seconds':stats([s['cooldown']['seconds'] for s in samples if 'cooldown' in s]),'cooldown_extra_poll_runs':sum(s.get('cooldown',{}).get('checks',0)>1 for s in samples),
        'gpu_sysfs_permission_denied_before_runs':denied,'gpu_frequency_and_busy_available':False,'in_run_frequency_trace_available':False,
        'limitations':'Before/after snapshots; context switches cover load+tune+warmup+measured+exit. No GPU frequency/busy access, no energy. Correlations do not identify cause.'}
    save(R/'analysis/device-state-summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
