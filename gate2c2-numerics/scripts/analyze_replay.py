from analyze import *
def main():
    runs=[];failed=[];excluded=[]
    primary=sorted(p.parent for p in (R/'results').glob('replay-*/session-status.json') if json.loads(p.read_text())['status']=='completed')[-1]
    for p in sorted((R/'results').glob('replay-*/*/result.json')):
        d=json.loads(p.read_text());d['path']=p.parent
        if not d['valid']:failed.append(str(p.relative_to(R)));continue
        if p.parent.parent!=primary:
            excluded.append({'directory':str(p.parent.relative_to(R)),'reason':'Earlier diagnostic tool/session; retained, not part of final paired replay with input refill and measured-entry verification'});continue
        source=R/json.loads((p.parent/'input-source.json').read_text())['file']
        snapshots=[p.parent/f'out/sample.r{i}.conv_input.f32' for i in [1,2]]
        if not all(x.exists() for x in snapshots):
            excluded.append({'directory':str(p.parent.relative_to(R)),'reason':'No per-execution conv input verification in early tool'});continue
        if not all(x.read_bytes()==source.read_bytes() for x in snapshots):
            excluded.append({'directory':str(p.parent.relative_to(R)),'reason':'Measured r1/r2 conv input differs from fixed source; not a valid same-input replay'});continue
        runs.append(d)
    results=[]
    def add(label,a,b,an='r1',bn='r1'):
        results.append(dict(label=label,kind=a['kind'],a_mode=f"{a['backend']}-{a['precision']}-{a['memory']}",b_mode=f"{b['backend']}-{b['precision']}-{b['memory']}",**metrics(a['path']/f'out/sample.{an}.f32',b['path']/f'out/sample.{bn}.f32')))
    groups={}
    for d in runs:
        meta=json.loads((d['path']/'out/sample.meta.json').read_text())
        assert len(meta['runs'])==3
        for run in meta['runs']:
            assert run['exit_code']==run['wait']==0
            assert sum(x['type']=='Convolution' for x in run['ops'])==1
            assert all(x['type'] in ['Convolution','Raster'] for x in run['ops'])
            for op in run['ops']:
                if op['type']=='Convolution':assert op['backend_type']==(3 if d['backend']=='opencl' else (13 if d['precision']=='low' else 0))
        src=R/json.loads((d['path']/'input-source.json').read_text())['file']
        results.append(dict(label='input_roundtrip',kind=d['kind'],backend=d['backend'],**metrics(src,d['path']/'out/sample.input.f32')))
        add('repeat_0_1',d,d,'r0','r1');add('repeat_1_2',d,d,'r1','r2')
        groups[(d['kind'],d['backend'],d['precision'],d['memory'])]=d
    for kind in ['synthetic','natural']:
        for precision in ['low','high']:
            a=groups.get((kind,'cpu',precision,'low'));b=groups.get((kind,'opencl',precision,'low'))
            if a and b:add('CPU_vs_GPU_same_input',a,b)
        ref=groups.get((kind,'cpu','high','high'))
        if ref:
            for (k,backend,precision,memory),b in groups.items():
                if k==kind and b is not ref:add('CPU_float_weight_reference',ref,b)
        for (k,backend,precision,memory),a in groups.items():
            if k!=kind or precision!='low' or memory!='low':continue
            full=sorted((R/'results').glob(f'checkpoints-*/{backend}-low-{kind}-checkpoints-p0/out/sample.r0._layers_0_self_attn_q_proj_Linear.f32'))[-1]
            results.append(dict(label='replay_vs_full',kind=kind,backend=backend,**metrics(full,a['path']/'out/sample.r1.f32')))
    warmup=[]
    for d in runs:
        src=R/json.loads((d['path']/'input-source.json').read_text())['file']
        m=metrics(src,d['path']/'out/sample.r0.conv_input.f32')
        if not m['identical_bytes']:warmup.append(dict(kind=d['kind'],backend=d['backend'],precision=d['precision'],**m))
    out={'primary_session':str(primary.relative_to(R)),'valid_processes':len(runs),'failed_processes':failed,'excluded_processes':excluded,'warmup_before_callback_input_mismatches':warmup,'measured_replay_indices':[1,2],'comparisons':results}
    (R/'analysis/replay.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    for m in results:
        if m['label'] not in ['input_roundtrip','repeat_0_1','repeat_1_2']:print(m['label'],m['kind'],m.get('a_mode',m.get('backend')),m.get('b_mode',''),m.get('relative_rmse'),m.get('max_abs'))
if __name__=='__main__':main()
