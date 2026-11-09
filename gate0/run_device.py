"""Run one explicitly selected Gate 0 device stage; no performance baseline sweep."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent
ADB=r'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe'
SERIAL='ee19377b'
MODE=sys.argv[1]
assert MODE in {'deploy','help','demo','bench'}
STAMP=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
DIRECTORY=ROOT/'evidence/runtime'/f'{STAMP}-{MODE}'
DIRECTORY.mkdir(parents=True)
RECORDS=[]

def run(label,args,timeout=90):
    command=[ADB,'-s',SERIAL,*args]
    started=datetime.now(timezone.utc).isoformat()
    timer=time.monotonic()
    print(f'Running {label}',flush=True)
    try:
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        stdout,stderr,code=result.stdout,result.stderr,result.returncode
    except subprocess.TimeoutExpired as error:
        stdout,stderr,code=error.stdout or b'',error.stderr or b'',124
    (DIRECTORY/f'{label}.stdout.txt').write_bytes(stdout)
    (DIRECTORY/f'{label}.stderr.txt').write_bytes(stderr)
    (DIRECTORY/f'{label}.exit.txt').write_text(str(code)+'\n')
    record={'label':label,'command':command,'started_at_utc':started,
            'elapsed_seconds':round(time.monotonic()-timer,3),'exit_code':code}
    RECORDS.append(record)
    (DIRECTORY/'commands.json').write_text(json.dumps(RECORDS,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{label}: exit={code}, seconds={record["elapsed_seconds"]}',flush=True)
    if code:
        print(stderr.decode('utf-8',errors='replace'),flush=True)
        raise RuntimeError(f'{label} failed with exit {code}; raw logs retained in {DIRECTORY}')
    return stdout

status={'mode':MODE,'directory':str(DIRECTORY),'stage_completed':False,
        'scope':'Gate 0 only. Demo output and benchmark results require separate review.'}
try:
    assert run('device-state',['get-state']).strip()==b'device'
    remote_file=ROOT/'evidence/runtime/remote-path.txt'
    if MODE=='deploy':
        remote=f'/data/local/tmp/mnn-gate0-{STAMP}'
        remote_file.write_text(remote+'\n')
        run('mkdir',['shell','mkdir','-p',remote])
        for name in ['llm_demo','llm_bench','libMNN.so']:
            path=ROOT/'staging'/name
            assert path.stat().st_size>0
            run('push-'+name,['push',str(path),remote+'/'],timeout=120)
        model=ROOT/'assets/Qwen3-0.6B-MNN'
        run('push-model',['push',str(model),remote+'/'],timeout=180)
        run('chmod',['shell',f'chmod 755 {remote}/llm_demo {remote}/llm_bench'])
        prompt=ROOT/'staging/prompt.txt'
        prompt.write_text('请用一句话介绍北京。\n',encoding='utf-8')
        run('push-prompt',['push',str(prompt),remote+'/'])
        files={name:ROOT/'staging'/name for name in ['llm_demo','llm_bench','libMNN.so','prompt.txt']}
        for name in ['config.json','config.cpu.json','llm_config.json','llm.mnn','llm.mnn.weight','tokenizer.txt']:
            files['Qwen3-0.6B-MNN/'+name]=model/name
        raw=run('remote-sha256',['shell',f'cd {remote} && sha256sum '+ ' '.join(files)],timeout=120)
        remote_hashes={line.split(None,1)[1].strip():line.split(None,1)[0] for line in raw.decode().splitlines()}
        verified=[]
        for name,path in files.items():
            with path.open('rb') as file: digest=hashlib.file_digest(file,'sha256').hexdigest()
            assert remote_hashes[name]==digest,(name,remote_hashes.get(name),digest)
            verified.append({'file':name,'sha256':digest,'host_device_match':True})
        (DIRECTORY/'deployment-hashes.json').write_text(json.dumps(verified,indent=2))
        print(f'Host/device SHA256 matched for {len(verified)} files',flush=True)
    else:
        remote=remote_file.read_text().strip()
        prefix=f'cd {remote} && LD_LIBRARY_PATH=. '
        if MODE=='help':
            output=run('llm-bench-help',['shell',prefix+'./llm_bench --help'])
            print(output.decode('utf-8',errors='replace'),flush=True)
        elif MODE=='demo':
            # Presence of fifth argv enables no-thinking in this pinned upstream demo.
            output=run('llm-demo',['shell',prefix+'./llm_demo Qwen3-0.6B-MNN/config.cpu.json prompt.txt 64 no_thinking'],timeout=180)
            print(output.decode('utf-8',errors='replace'),flush=True)
        elif MODE=='bench':
            command='./llm_bench -m Qwen3-0.6B-MNN/config.cpu.json -a cpu -t 4 -p 0 -n 0 -pg 128,64 -rep 1 -c 2 -mmp 0 -qa 0 -fa 1 -load false -j bench-smoke.json'
            output=run('llm-bench-smoke',['shell',prefix+command],timeout=300)
            print(output.decode('utf-8',errors='replace'),flush=True)
            run('pull-bench-json',['pull',remote+'/bench-smoke.json',str(DIRECTORY/'bench-smoke.json')])
    status['remote_path']=remote
    status['stage_completed']=True
except Exception as error:
    status['error']=str(error)
    raise
finally:
    (DIRECTORY/'stage-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Evidence: {DIRECTORY}',flush=True)
