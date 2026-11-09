"""Separate RSS/PSS sampling diagnostics; never pooled with baseline timings."""
from pathlib import Path
from datetime import datetime,timezone
import json,re,sys,uuid
from run_bench import ROOT,Runner,load,save,parse_benchmark

def main():
    config=load(ROOT/'configs/cpu.json')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    directory=ROOT/'diagnostics'/('memory-'+stamp);directory.mkdir(parents=True,exist_ok=False)
    runner=Runner(config,directory)
    remote=config['remote_root']+'/gate1-memory-'+stamp
    status={'scope':'Independent memory diagnostic; all associated throughput excluded from baseline','started_at_utc':datetime.now(timezone.utc).isoformat(),'samples':[],'status':'running'}
    save(directory/'protocol.json',dict(config,diagnostic='memory',poll_interval_seconds=.5))
    try:
        out,err,rec=runner.shell('mkdir','mkdir -p '+remote,directory)
        if rec['exit_code']:raise RuntimeError('mkdir failed')
        out,err,rec=runner.adb('push-monitor',['push',str(ROOT/'scripts/sample_memory.sh'),remote+'/sample_memory.sh'],directory)
        if rec['exit_code']:raise RuntimeError('monitor push failed')
        for i,(pp,tg) in enumerate(config['workloads'],1):
            local=directory/f'pp{pp}-tg{tg}';local.mkdir()
            runner.cool(local,15)
            runner.state('before',local)
            dest=remote+f'/pp{pp}-tg{tg}'
            out,err,rec=runner.shell('diagnostic',f'sh {remote}/sample_memory.sh {config["remote_root"]} {pp} {tg} {dest}',local,180)
            runner.state('after',local)
            _,_,pull=runner.adb('pull',['pull',dest,str(local/'device')],local)
            if rec['exit_code'] or pull['exit_code']:raise RuntimeError('memory diagnostic or artifact pull failed')
            raw=(local/'device/memory.txt').read_text(encoding='utf-8').replace('\r','')
            blocks=raw.split('@@SAMPLE ')[1:]
            expected_pid=int((local/'device/pid.txt').read_text().strip())
            rows=[]
            for block in blocks:
                row={'device_time_and_uptime':block.splitlines()[0]}
                name_match=re.search(r'^Name:\s*(\S+)',block,re.M)
                pid_match=re.search(r'^Pid:\s*(\d+)',block,re.M)
                row['process_name']=name_match.group(1) if name_match else None
                row['pid']=int(pid_match.group(1)) if pid_match else None
                row['target_identity_confirmed']=row['pid']==expected_pid and row['process_name']=='llm_bench'
                for key in ['VmRSS','VmHWM','Pss','Rss','SwapPss','VmSwap']:
                    m=re.search(r'^'+key+r':\s*(\d+)\s*kB',block,re.M)
                    row[key+'_kib']=int(m.group(1)) if m else None
                rows.append(row)
            parsed=load(local/'device/benchmark.json');parse_benchmark(parsed,pp,tg,config)
            def maximum(key):
                vals=[r[key] for r in rows if r['target_identity_confirmed'] and r.get(key) is not None]
                return max(vals) if vals else None
            item={'prompt_tokens':pp,'generated_tokens':tg,'process_exit':rec['exit_code'],'sample_count':len(rows),
                  'pss_available':any(r['target_identity_confirmed'] and r.get('Pss_kib') is not None for r in rows),
                  'identity_confirmed_snapshots':sum(r['target_identity_confirmed'] for r in rows),
                  'max_observed_pss_kib':maximum('Pss_kib'),'max_observed_rss_kib':maximum('VmRSS_kib'),
                  'max_observed_vmhwm_kib':maximum('VmHWM_kib'),'samples':rows,
                  'warning':'PSS/RSS polling maxima are sampled lower bounds; no stage labels; diagnostic throughput excluded'}
            save(local/'memory-summary.json',item);status['samples'].append(item)
            print(f'{pp}+{tg}: memory samples={len(rows)}, PSS={item["max_observed_pss_kib"]}, RSS={item["max_observed_rss_kib"]}',flush=True)
        status['status']='completed'
    except Exception as error:
        status['status']='failed';status['error']=str(error)
    finally:
        status['ended_at_utc']=datetime.now(timezone.utc).isoformat();save(directory/'diagnostic-status.json',status)
        print('Memory diagnostic:',directory,flush=True)
    return 0 if status['status']=='completed' else 1

if __name__=='__main__':sys.exit(main())
