from pathlib import Path
import array,math,json,hashlib,sys
R=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
def read(p):
    a=array.array('f');a.frombytes(p.read_bytes());
    if sys.byteorder!='little':a.byteswap()
    return a
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metrics(pa,pb,logits=False):
    a,b=read(pa),read(pb);assert len(a)==len(b) and a
    finite=all(math.isfinite(v) for v in a) and all(math.isfinite(v) for v in b)
    m={'elements':len(a),'all_finite':finite,'identical_bytes':pa.read_bytes()==pb.read_bytes(),'a':str(pa.relative_to(R.parent)),'b':str(pb.relative_to(R.parent))}
    if not finite:return m
    aa=math.fsum(x*x for x in a);bb=math.fsum(x*x for x in b);err=math.fsum((y-x)**2 for x,y in zip(a,b));dot=math.fsum(x*y for x,y in zip(a,b))
    m.update(relative_rmse=math.sqrt(err/aa) if aa else (0 if not err else None),cosine=dot/math.sqrt(aa*bb) if aa*bb else None,
        max_abs=max(abs(x-y) for x,y in zip(a,b)),mean_abs=math.fsum(abs(x-y) for x,y in zip(a,b))/len(a),
        a_min=min(a),a_max=max(a),b_min=min(b),b_max=max(b),bound_fraction=sum(abs(y-x)<=.1+.02*abs(x) for x,y in zip(a,b))/len(a))
    if logits:
        ia=sorted(range(len(a)),key=lambda i:a[i],reverse=True)[:5];ib=sorted(range(len(b)),key=lambda i:b[i],reverse=True)[:5]
        m.update(a_top5=[{'id':i,'value':a[i]} for i in ia],b_top5=[{'id':i,'value':b[i]} for i in ib],a_margin=a[ia[0]]-a[ia[1]],b_margin=b[ib[0]]-b[ib[1]],top1_same=ia[0]==ib[0],top5_overlap=len(set(ia)&set(ib)),top5_order_same=ia==ib)
        m['exploratory_passed']=m['relative_rmse']<=.02 and m['cosine']>=.999 and m['bound_fraction']>=.999
    return m
def main():
    runs=[]
    for p in sorted((R/'results').glob('*/*/result.json')):
        d=json.loads(p.read_text());d['path']=p.parent
        if d['valid'] and 'mode' in d:runs.append(d)
    comparisons=[]
    def add(label,a,b,sa='logits',sb='logits'):
        ma=json.loads((a['path']/'out/sample.r0.meta.json').read_text());mb=json.loads((b['path']/'out/sample.r0.meta.json').read_text())
        assert json.loads((a['path']/'out/sample.ids.json').read_text())==json.loads((b['path']/'out/sample.ids.json').read_text())
        if sa=='logits':assert ma['shape']==mb['shape']
        else:
            ca=next(x for x in ma['checkpoints'] if x['key']==sa);cb=next(x for x in mb['checkpoints'] if x['key']==sb)
            assert ca['host_shape']==cb['host_shape'] and ca['op_name']==cb['op_name'] and ca['phase']==cb['phase']
        comparisons.append(dict(label=label,kind=a['kind'],precision=a['precision'],checkpoint=sa,**metrics(a['path']/f'out/sample.r0.{sa}.f32',b['path']/f'out/sample.r0.{sb}.f32',sa in ['logits','_lm_lm_head_Linear'])))
    # Each backend's within-process repeatability (a complete new prefill, not repeated pointer reads).
    for a in runs:
        for p in (a['path']/'out').glob('sample.r0.*.f32'):
            q=p.with_name(p.name.replace('.r0.','.r1.'));comparisons.append(dict(label='within_process',kind=a['kind'],precision=a['precision'],backend=a['backend'],mode=a['mode'],checkpoint=p.name[10:-4],**metrics(p,q,'.logits.' in p.name)))
    canonical={}
    for a in runs:
        if a['mode']=='off' and a['process']==0:canonical[(a['backend'],a['precision'],a['kind'])]=a
    for (backend,precision,kind),a in canonical.items():
        for b in runs:
            if (b['backend'],b['precision'],b['kind'])!=(backend,precision,kind):continue
            if b['mode']=='checkpoints':add('debug_vs_off',a,b)
            elif b['process']==1:add('cross_process',a,b)
        if precision=='low':
            b=canonical.get((backend,'high',kind))
            if b:add('low_vs_high',a,b)
            old=R.parent/f'gate2c-opencl/results/logits-20261108T195947Z-5aba2f/{backend}-{kind}/logits.f32'
            comparisons.append(dict(label='C1_vs_C2',kind=kind,backend=backend,**metrics(old,a['path']/'out/sample.r0.logits.f32',True)))
    for precision in ['low','high']:
        for kind in ['synthetic','natural']:
            a=canonical.get(('cpu',precision,kind));b=canonical.get(('opencl',precision,kind))
            if a and b:add('CPU_vs_GPU',a,b)
            da=[x for x in runs if x['backend']=='cpu' and x['precision']==precision and x['kind']==kind and x['mode']=='checkpoints']
            db=[x for x in runs if x['backend']=='opencl' and x['precision']==precision and x['kind']==kind and x['mode']=='checkpoints']
            if da and db:
                a,b=da[-1],db[-1];ma=json.loads((a['path']/'out/sample.r0.meta.json').read_text());mb=json.loads((b['path']/'out/sample.r0.meta.json').read_text())
                ka={x['key'] for x in ma['checkpoints']};kb={x['key'] for x in mb['checkpoints']};assert ka==kb,(ka,kb)
                for key in sorted(ka):add('checkpoint_CPU_vs_GPU',a,b,key,key)
    out={'valid_process_count':len(runs),'failed_processes':[str(p) for p in (R/'results').glob('*/*/result.json') if not json.loads(p.read_text())['valid']],
        'independent_inputs':2,'comparisons':comparisons}
    (R/'analysis').mkdir(exist_ok=True);(R/'analysis/metrics.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    for m in comparisons:
        if m['label'] in ['CPU_vs_GPU','checkpoint_CPU_vs_GPU']:print(m['label'],m['precision'],m['kind'],m['checkpoint'],m.get('relative_rmse'),m.get('max_abs'))
    print('Valid processes',len(runs),'comparisons',len(comparisons))
if __name__=='__main__':main()
