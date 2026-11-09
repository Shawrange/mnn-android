from run import *
assert not (R/'freeze.json').exists()
p=sorted((R/'results').glob('pilot-*'))[-1]
assert load(p/'session-status.json')['status']=='completed'
for d in p.glob('*/sample.json'):
    s=load(d);assert s['status']=='success' and abs(load(d.parent/'benchmark.json')['modelSize']-450810338/1024**3)<1e-9
f=sorted((R/'results').glob('functional-*'))[-1];assert load(f/'session-status.json')['status']=='completed'
for b in ['cpu','opencl']:
    v=load(f/b/'count-contract.json')
    for x in v['runs']:assert x['gen_seq_len']==x['tg']==len(x['output_ids']) and x['kv_after']==x['pp']+x['tg']
rng=random.Random(20261109);schedule=[]
for block in range(1,7):
    loads=[[32,64],[128,64],[128,256]];rng.shuffle(loads)
    for pp,tg in loads:
        backends=['cpu','opencl'];rng.shuffle(backends)
        for b in backends:schedule.append(dict(block=block,backend=b,pp=pp,tg=tg))
save(R/'configs/schedule.json',schedule)
for pp in [32,128]:save(R/'configs'/f'input-{pp}.json',[16]*pp)
save(R/'configs/experiment.json',dict(C,formal_processes=36,independent_processes_per_cell=6,minimum_gap_seconds=15,seed=20261109,requested_runtime={'precision':2,'memory':2,'power':0,'t':4,'dyo':0,'qa':0,'fa':1,'ignore_eos':True,'async':False,'greedy':True,'reuse_kv':False},effective_runtime={'dynamic_option':0,'attention_mode':8,'cpu_threads':4,'opencl_mode_bits':580}))
files=['protocol.md','scripts/run.py','scripts/adb_utils.py','scripts/count_probe.cpp','scripts/analyze.py','scripts/test_analysis.py','deployment.json']
files += [str(x.relative_to(R)) for parent in ['configs','staging'] for x in (R/parent).rglob('*') if x.is_file()]
save(R/'freeze.json',{'frozen_at_utc':utc(),'seed':20261109,'formal_process_count':36,'successful_pilot':str(p.relative_to(R)),'functional_session':str(f.relative_to(R)),'sha256':{n:sha(R/n) for n in files}})
print('Frozen 36-run protocol at',load(R/'freeze.json')['frozen_at_utc'])
