"""Small stdlib runner around the pinned official llm_bench, one JSON sample/process."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,platform,random,re,shlex,shutil,subprocess,sys,time,uuid

ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
def utc(): return datetime.now(timezone.utc).isoformat()
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value): Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def parse_benchmark(data,pp,tg,config):
    for key,value in {'backend':'CPU','threads':4,'precision':2,'memory':2,'power':0,'quantKv':0,'flashAttention':1,'useMmap':False}.items():
        if data.get(key)!=value: raise ValueError(f'JSON config mismatch: {key}={data.get(key)!r}')
    if len(data.get('results',[]))!=1: raise ValueError('Expected exactly one result')
    result=data['results'][0]
    if result.get('type')!='prefill_and_decode' or result.get('prompt_len')!=pp or result.get('generate_len')!=tg:
        raise ValueError('Wrong workload/type')
    for key in ['prefill_tps','decode_tps']:
        if not isinstance(result.get(key),(int,float)) or not math.isfinite(result[key]) or result[key]<=0:
            raise ValueError(f'Invalid throughput: {key}')
    return {'prefill_tps':result['prefill_tps'],'decode_tps':result['decode_tps'],
            'prefill_ms_derived':1000*pp/result['prefill_tps'],'decode_ms_derived':1000*tg/result['decode_tps'],
            'effective_dynamic_option':0 if 0<pp<=300 else 8,
            'ttft_ms':None,'pss_kib':None}

def parse_state(text):
    def number(pattern):
        m=re.search(pattern,text,re.M)
        return float(m.group(1)) if m else None
    battery=number(r'^\s*temperature:\s*(\d+)')
    current=text.split('Current temperatures from HAL:',1)[-1].split('Current cooling devices from HAL:',1)[0] if 'Current temperatures from HAL:' in text else ''
    temps={name:float(value) for value,kind,name in re.findall(r'Temperature\{mValue=([\d.]+), mType=(\d+), mName=([^,}]+)',current)}
    cpus=[v for k,v in temps.items() if k.startswith('CPU')]
    policies={}
    for policy,body in re.findall(r'@@POLICY (\S+)\n(.*?)(?=@@|\Z)',text,re.S):
        policies[policy]={key:val.strip() for key,val in re.findall(r'^([^=\n]+)=(.*)$',body,re.M)}
    return {'battery_c':battery/10 if battery is not None else None,'battery_percent':number(r'^\s*level:\s*(\d+)'),
            'usb_powered': 'USB powered: true' in text,'thermal_status':number(r'^Thermal Status:\s*(\d+)'),
            'hal_temperatures_c':temps,'skin_c':temps.get('skin'),'cpu_max_c':max(cpus) if cpus else None,
            'policies':policies,'mem_available_kib':number(r'^MemAvailable:\s*(\d+)'),
            'mem_free_kib':number(r'^MemFree:\s*(\d+)'),'screen_state':re.findall(r'(?:mWakefulness|Display Power: state)\s*[=:]\s*(\S+)',text),
            'loadavg':re.search(r'@@LOAD\n([^\n]+)',text).group(1) if re.search(r'@@LOAD\n([^\n]+)',text) else None}

STATE_COMMAND='''echo @@BATTERY
dumpsys battery
echo @@THERMAL
dumpsys thermalservice
for p in /sys/devices/system/cpu/cpufreq/policy*; do
 echo "@@POLICY ${p##*/}"
 for f in scaling_cur_freq scaling_min_freq scaling_max_freq cpuinfo_max_freq scaling_governor related_cpus; do
  printf '%s=' "$f"; cat "$p/$f"
 done
done
echo @@MEMORY
cat /proc/meminfo
echo @@LOAD
cat /proc/loadavg
echo @@POWER
dumpsys power | grep -E 'mWakefulness=|Display Power: state='
'''

class Runner:
    def __init__(self,config,directory):
        self.c=config; self.root=directory
    def adb(self,label,args,directory,timeout=45):
        command=[self.c['adb'],'-s',self.c['serial'],*args]
        started=utc(); timer=time.perf_counter()
        try:
            p=subprocess.run(command,capture_output=True,timeout=timeout)
            out,err,code=p.stdout,p.stderr,p.returncode
        except subprocess.TimeoutExpired as e:
            out,err,code=e.stdout or b'',e.stderr or b'',124
        (directory/f'{label}.stdout.txt').write_bytes(out)
        (directory/f'{label}.stderr.txt').write_bytes(err)
        record={'command':command,'started_at_utc':started,'ended_at_utc':utc(),'elapsed_seconds':time.perf_counter()-timer,'exit_code':code}
        save(directory/f'{label}.command.json',record)
        (directory/f'{label}.exit.txt').write_text(str(code)+'\n')
        return out,err,record
    def shell(self,label,command,directory,timeout=45):return self.adb(label,['shell',command],directory,timeout)
    def state(self,label,directory):
        out,err,record=self.shell(label,STATE_COMMAND,directory)
        data=parse_state(out.decode('utf-8',errors='replace'))
        data['query_exit_code']=record['exit_code']
        save(directory/f'{label}.json',data)
        return data
    def cool(self,directory,minimum):
        started=time.monotonic()
        if minimum:time.sleep(minimum)
        states=[]
        while True:
            state=self.state(f'cool-{len(states):02}',directory); states.append(state)
            limits=self.c['cooling']
            ready=state['query_exit_code']==0 and all(state[k] is not None and state[k]<=limits[lim] for k,lim in [('skin_c','max_skin_c'),('battery_c','max_battery_c'),('cpu_max_c','max_current_cpu_c')]) and state['thermal_status']==0
            if ready:break
            if time.monotonic()-started>=limits['max_wait_seconds']:raise RuntimeError('Cooling timeout: no further inference; raw states saved')
            print('Waiting for declared temperature window...',flush=True)
            time.sleep(limits['poll_seconds'])
        return {'seconds':time.monotonic()-started,'checks':len(states)}
    def preflight(self):
        out,err,rec=self.adb('device',['get-state'],self.root)
        if rec['exit_code'] or out.strip()!=b'device':raise RuntimeError('Target device unavailable')
        gate0=Path(self.c['gate0_root'])
        for name in ['evidence/build/inspection-summary.json','evidence/build/CMakeCache.txt','evidence/build/build-environment.txt','evidence/model/model-lock.json','evidence/verification-summary.json']:
            shutil.copyfile(gate0/name,self.root/Path(name).name)
        shutil.copyfile(gate0/'assets/Qwen3-0.6B-MNN/config.cpu.json',self.root/'config.cpu.json')
        shutil.copyfile(gate0/'assets/Qwen3-0.6B-MNN/llm_config.json',self.root/'llm_config.json')
        source=['wsl','-d','Ubuntu','--','git','-C','/home/shawrange/src/MNN-3.6.2']
        pin=subprocess.run(source+['rev-parse','HEAD'],capture_output=True)
        clean=subprocess.run(source+['status','--porcelain','--untracked-files=no'],capture_output=True)
        save(self.root/'source-state.json',{'pin_exit':pin.returncode,'commit':pin.stdout.decode().strip(),'status_exit':clean.returncode,'status':clean.stdout.decode(),'stderr':(pin.stderr+clean.stderr).decode('utf-8',errors='replace')})
        if pin.returncode or pin.stdout.decode().strip()!=self.c['mnn_commit'] or clean.returncode or clean.stdout.strip():raise RuntimeError('Source pin/cleanliness check failed')
        expected={a['file']:a['sha256'] for a in load(self.root/'inspection-summary.json')['artifacts']}
        files={'llm_bench':gate0/'staging/llm_bench','libMNN.so':gate0/'staging/libMNN.so'}
        for name in ['config.cpu.json','llm_config.json','llm.mnn','llm.mnn.weight','tokenizer.txt']:
            files['Qwen3-0.6B-MNN/'+name]=gate0/'assets/Qwen3-0.6B-MNN'/name
        hashes={}
        for name,path in files.items():
            with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            hashes[name]=digest
            if name in expected and digest!=expected[name]:raise RuntimeError('Host artifact changed')
        lock=load(self.root/'model-lock.json')
        for item in lock['files']:
            if item.get('expected_lfs_sha256') and hashes['Qwen3-0.6B-MNN/'+item['path']]!=item['expected_lfs_sha256']:raise RuntimeError('Model hash changed')
        out,err,rec=self.shell('remote-hashes','cd '+self.c['remote_root']+' && sha256sum '+' '.join(files),self.root)
        remote={line.split(None,1)[1].strip():line.split(None,1)[0] for line in out.decode().splitlines()}
        if rec['exit_code'] or remote!=hashes:raise RuntimeError('Remote hashes differ from pinned local assets')
        save(self.root/'verified-assets.json',hashes)
        self.shell('device-metadata','getprop ro.product.model; getprop ro.soc.model; getprop ro.build.fingerprint; getprop ro.build.version.sdk; getprop ro.product.cpu.abilist; getconf PAGESIZE; uname -a; id',self.root)
        self.shell('help','cd '+self.c['remote_root']+' && LD_LIBRARY_PATH=. ./llm_bench --help',self.root)
        self.shell('time-capability','/system/bin/time -v sleep 0.01',self.root)
    def sample(self,index,round_id,pp,tg,remote,cooldown):
        directory=self.root/f'{index:03}-r{round_id:02}-pp{pp}-tg{tg}'
        directory.mkdir(exist_ok=False)
        sample={'index':index,'round':round_id,'prompt_tokens':pp,'generated_tokens':tg,'status':'started','started_at_utc':utc(),'evidence_status':'measured','ttft_ms':None,'pss_kib':None}
        save(directory/'sample.json',sample)
        try:
            sample['cooldown']=self.cool(directory,cooldown)
            sample['before']=self.state('before',directory)
            output=f'{remote}/s{index:03}.json'
            args=['./llm_bench','-m',self.c['remote_config'],'-a','cpu','-t','4','-p','0','-n','0','-pg',f'{pp},{tg}','-rep','1','-c','2','--memory','2','--power','0','-dyo','0','-mmp','0','-qa','0','-fa','1','-load','false','-j',output]
            command='cd '+self.c['remote_root']+' && LD_LIBRARY_PATH=. /system/bin/time -v '+shlex.join(args)
            out,err,rec=self.shell('benchmark',command,directory,self.c['timeout_seconds'])
            sample['process_wall_seconds_host']=rec['elapsed_seconds']
            sample['exit_code']=rec['exit_code']
            sample['after']=self.state('after',directory)
            raw_json,pullerr,pullrec=self.adb('pull-json',['pull',output,str(directory/'benchmark.json')],directory)
            sample['json_pull_exit_code']=pullrec['exit_code']
            if rec['exit_code'] or pullrec['exit_code']:raise ValueError('Benchmark or JSON pull failed')
            if re.search(rb'Incomplete sample|INTERNAL_ERROR|LLM init error|CANNOT LINK|Error:|\[Error\]',out+err):raise ValueError('Benchmark error marker')
            sample.update(parse_benchmark(load(directory/'benchmark.json'),pp,tg,self.c))
            stderr=err.decode('utf-8',errors='replace')
            for key,pattern in [('max_rss_kib',r'Max RSS \(KiB\):\s*(\d+)'),('whole_process_wall_seconds_device',r'Real time \(s\):\s*([\d.]+)'),('major_faults',r'Major faults:\s*(\d+)'),('minor_faults',r'Minor faults:\s*(\d+)')]:
                match=re.search(pattern,stderr)
                sample[key]=float(match.group(1)) if match else None
            match=re.search(rb'decode wall speed \(incl. sampling\):\s*([\d.]+)',out)
            sample['decode_wall_tps_rounded']=float(match.group(1)) if match else None
            sample['status']='success'
        except Exception as error:
            sample['status']='failed'; sample['error']=str(error)
        finally:
            sample['ended_at_utc']=utc(); save(directory/'sample.json',sample)
        print(f'{index:03} r{round_id} {pp}+{tg}: {sample["status"]} prefill={sample.get("prefill_tps")} decode={sample.get("decode_tps")} skin={sample.get("after",{}).get("skin_c")} battery={sample.get("after",{}).get("battery_c")}',flush=True)
        return sample

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default=str(ROOT/'configs/cpu.json'));ap.add_argument('--phase',choices=['pilot','baseline'],required=True);ap.add_argument('--rounds',type=int,required=True);ap.add_argument('--cooldown',type=float,required=True);args=ap.parse_args()
    if args.rounds<1 or args.cooldown<0:ap.error('Positive rounds and nonnegative cooldown required')
    config=load(args.config)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    directory=ROOT/'results'/f'{args.phase}-{stamp}';directory.mkdir(parents=True,exist_ok=False)
    save(directory/'protocol.json',dict(config,phase=args.phase,rounds=args.rounds,cooldown_seconds=args.cooldown,started_at_utc=utc(),python=sys.version,host_platform=platform.platform()))
    runner=Runner(config,directory); samples=[];status={'status':'running','started_at_utc':utc()}
    try:
        runner.preflight()
        remote=config['remote_root']+'/gate1-'+stamp
        out,err,rec=runner.shell('mkdir','mkdir -p '+remote,directory)
        if rec['exit_code']:raise RuntimeError('Remote result directory failed')
        schedule=[];randomizer=random.Random(config['order_seed'])
        for r in range(1,args.rounds+1):
            workloads=config['workloads'].copy();randomizer.shuffle(workloads)
            for pp,tg in workloads:schedule.append({'round':r,'pp':pp,'tg':tg})
        save(directory/'schedule.json',schedule)
        for i,item in enumerate(schedule,1):
            result=runner.sample(i,item['round'],item['pp'],item['tg'],remote,args.cooldown)
            samples.append(result)
            if result['status']!='success':raise RuntimeError('Stopped after failed sample; failure retained')
        status['status']='completed'
    except Exception as error:
        status['status']='failed';status['error']=str(error)
    finally:
        status.update(ended_at_utc=utc(),attempted=len(samples),successful=sum(s['status']=='success' for s in samples),directory=str(directory))
        save(directory/'session-status.json',status)
        print(json.dumps(status,ensure_ascii=False),flush=True)
    return 0 if status['status']=='completed' else 1

if __name__=='__main__':sys.exit(main())
