from run import *
def main():
    check_freeze();selected=load(R/'analysis/logits-selection.json');cases={c['id']:c for c in [json.loads(x) for x in (R/'datasets/formal.jsonl').read_text(encoding='utf-8').splitlines()]}
    d=R/'results'/('diagnostics-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]);d.mkdir(parents=True)
    remote='/data/local/tmp/mnn-gate2c4-'+d.name;r=Runner(C,d);save(d/'protocol.json',dict(C,remote=remote,started_at_utc=utc(),freeze_sha256=sha(R/'freeze.json'),selection_sha256=sha(R/'analysis/logits-selection.json'),scope='fixed-prefix full-Prefill replay; not incremental teacher forcing'))
    shutil.copyfile(__file__,d/'runner.py');save(d/'selection.json',selected);status={'status':'running','completed':[]}
    try:
        deploy(r,d,remote);r.state('before',d)
        for item in selected:
            ident=item['id']
            for label,prefix in [('first-token',[]),('first-split',item['common_prefix_ids'])]:
                p=d/(ident+'-'+label);p.mkdir()
                req={'id':ident+'-'+label,'input':item['input'],'reference':item['reference'],'prefix_ids':prefix}
                for backend in ['cpu','opencl']:
                    v=run_case(r,p,remote,backend,req,'logits')
                    if not v['runtime_ok']:raise RuntimeError('Logits replay failed: '+req['id']+' '+backend)
                    status['completed'].append(req['id']+'-'+backend)
                print('Captured logits',ident,label,flush=True)
        discordant=[x for x in selected if x['cpu_success']!=x['gpu_success']][:6]
        for rep in [1,2]:
            p=d/f'repeat-{rep}';p.mkdir()
            for item in discordant:
                req=cases[item['id']].copy();req['id']=req['id']+f'-repeat{rep}'
                for backend in ['cpu','opencl']:
                    v=run_case(r,p,remote,backend,req)
                    if not v['runtime_ok']:raise RuntimeError('Repeat runtime failure')
                print('Repeated',req['id'],flush=True)
        r.state('after',d);status['status']='completed'
    except Exception as e:status.update(status='interrupted',error=str(e));raise
    finally:status['ended_at_utc']=utc();save(d/'session-status.json',status)
    print(d,flush=True)
if __name__=='__main__':main()
