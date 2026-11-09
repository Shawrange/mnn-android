from run import *
import math,collections,csv
def wilson(k,n,z=1.959963984540054):
    p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;rad=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,mid-rad),min(1,mid+rad)]
def paired(rows):
    n=len(rows);a=sum(x['cpu_success'] and x['gpu_success'] for x in rows);b=sum(x['cpu_success'] and not x['gpu_success'] for x in rows);c=sum(not x['cpu_success'] and x['gpu_success'] for x in rows);both_bad=n-a-b-c
    delta=(c-b)/n;var=((b+c)-n*delta*delta)/(n-1) if n>1 else 0;se=math.sqrt(max(0,var/n));ci=[max(-1,delta-1.959963984540054*se),min(1,delta+1.959963984540054*se)]
    disc=b+c;p=1 if not disc else min(1,2*sum(math.comb(disc,j) for j in range(min(b,c)+1))/2**disc)
    # Descriptive conservative interval from simultaneous discordance-probability Wilson bounds.
    wc=wilson(c,n,2.241402727604947);wb=wilson(b,n,2.241402727604947)
    return dict(n=n,cpu_success=a+b,gpu_success=a+c,cpu_rate=(a+b)/n,gpu_rate=(a+c)/n,cpu_wilson95=wilson(a+b,n),gpu_wilson95=wilson(a+c,n),both_correct=a,cpu_only=b,gpu_only=c,both_wrong=both_bad,gpu_minus_cpu=delta,paired_normal95=ci,descriptive_conservative_delta_interval=[wc[0]-wb[1],wc[1]-wb[0]],mcnemar_exact_two_sided=p)
def select_logits(rows,cases):
    # Frozen in protocol: prioritize direction, then ID. No model outputs are judged by a new rubric.
    selected=[]
    for predicate,cap in [(lambda x:x['cpu_success'] and not x['gpu_success'],3),(lambda x:not x['cpu_success'] and x['gpu_success'],2),(lambda x:True,6)]:
        used=0
        for x in sorted(rows,key=lambda x:x['id']):
            if x['id'] in selected or not predicate(x) or x['cpu_tokens']==x['gpu_tokens']:continue
            selected.append(x['id']);used+=1
            if used>=cap or len(selected)>=6:break
        if len(selected)>=6:break
    if not selected:selected=[x['id'] for x in sorted(rows,key=lambda x:x['id']) if x['cpu_success'] and x['gpu_success']][:2]
    output=[]
    byid={c['id']:c for c in cases};rowsby={r['id']:r for r in rows}
    for ident in selected:
        x=rowsby[ident];cpu,gpu=x['cpu_tokens'],x['gpu_tokens'];first=0
        while first<min(len(cpu),len(gpu)) and cpu[first]==gpu[first]:first+=1
        cp=cpu[:first];c=byid[ident]
        output.append({'id':ident,'common_prefix_ids':cp,'first_divergence_index':first,'original_cpu_next':cpu[first] if first<len(cpu) else None,'original_gpu_next':gpu[first] if first<len(gpu) else None,'cpu_success':x['cpu_success'],'gpu_success':x['gpu_success'],'input':c['input'],'reference':c['variants'][0]})
    return output
def main():
    freeze=check_freeze();cases=[json.loads(x) for x in (R/'datasets/formal.jsonl').read_text(encoding='utf-8').splitlines()]
    complete=[p for p in sorted((R/'results').glob('formal-*')) if load(p/'session-status.json')['status']=='completed'];assert complete
    d=complete[-1];rows=[];failures={'cpu':collections.Counter(),'opencl':collections.Counter()};configfirst={};review=[]
    for c in cases:
        values={};scores={};tokens={}
        for b in ['cpu','opencl']:
            p=d/(c['id']+'-'+b);v=load(p/'result.json');g=grade(c,v);assert g==load(p/'score.json')
            meta=load(p/'device/sample.meta.json');assert meta['initial_kv']==0 and meta['thinking']==False
            cfg=load(p/'device/sample.config.json');assert cfg['sampler_type']=='greedy' and cfg['ignore_eos']==False and cfg['reuse_kv']==False and cfg['jinja']['context']['enable_thinking']==False
            if b not in configfirst:configfirst[b]=cfg
            assert cfg==configfirst[b]
            values[b]=v;scores[b]=g;tokens[b]=load(p/'device/sample.output_ids.json');failures[b].update(g['flags'])
        assert load(d/(c['id']+'-cpu')/'device/sample.input_ids.json')==load(d/(c['id']+'-opencl')/'device/sample.input_ids.json')
        assert (d/(c['id']+'-cpu')/'device/sample.rendered_prompt.txt').read_bytes()==(d/(c['id']+'-opencl')/'device/sample.rendered_prompt.txt').read_bytes()
        row={'id':c['id'],'category':c['category'],'cpu_success':scores['cpu']['success'],'gpu_success':scores['opencl']['success'],'cpu_text':values['cpu']['raw_text'],'gpu_text':values['opencl']['raw_text'],'cpu_flags':scores['cpu']['flags'],'gpu_flags':scores['opencl']['flags'],'cpu_tokens':tokens['cpu'],'gpu_tokens':tokens['opencl'],'same_tokens':tokens['cpu']==tokens['opencl'],'same_text':values['cpu']['raw_text']==values['opencl']['raw_text']}
        rows.append(row)
    configcpu=configfirst['cpu'].copy();configgpu=configfirst['opencl'].copy();configcpu.pop('backend_type');configgpu.pop('backend_type');assert configcpu==configgpu
    categories={cat:paired([r for r in rows if r['category']==cat]) for cat in ['classification','extraction','instruction','qa']};overall=paired(rows)
    targets=freeze['thresholds'];quality={}
    for b,key in [('cpu','cpu_success'),('opencl','gpu_success')]:
        fmt=sum(load(d/(c['id']+'-'+b)/'score.json')['format_valid'] for c in cases if c['category']=='extraction')
        eos=sum(load(d/(c['id']+'-'+b)/'result.json')['stopped'] for c in cases)
        noerror=not any(load(d/(c['id']+'-'+b)/'result.json')['process_exit'] or not load(d/(c['id']+'-'+b)/'result.json')['runtime_ok'] for c in cases)
        groups={cat:sum(r[key] for r in rows if r['category']==cat)>=targets[cat+'_min'] for cat in categories}
        success=sum(r[key] for r in rows)
        quality[b]={'successes':success,'category_gate':groups,'extraction_format_valid':fmt,'natural_eos':eos,'no_runtime_error':noerror,'quality_gate_met':all(groups.values()) and success>=targets['overall_min'] and fmt>=targets['extraction_format_min'] and eos>=targets['natural_eos_min'] and noerror}
    guards=overall['gpu_minus_cpu']>=targets['gpu_minus_cpu_min'] and overall['cpu_only']<=targets['cpu_only_max'] and overall['paired_normal95'][0]>=targets['paired_CI_lower_min'] and all(x['gpu_minus_cpu']>=targets['per_category_delta_min'] for x in categories.values())
    if quality['opencl']['quality_gate_met'] and guards:decision='A_pending_gpu_execution_evidence'
    elif not quality['cpu']['quality_gate_met'] and not quality['opencl']['quality_gate_met']:decision='C'
    elif quality['cpu']['quality_gate_met'] and (overall['gpu_minus_cpu']<=-.05 or any(x['gpu_minus_cpu']<=-.12 for x in categories.values())):decision='B_pending_repeats'
    else:decision='D'
    out={'formal_session':str(d.relative_to(R)),'freeze_sha256':sha(R/'freeze.json'),'independent_cases':100,'overall':overall,'categories':categories,'quality_gates':quality,'difference_guards_met':guards,'preliminary_decision':decision,'failure_counts':{b:dict(v) for b,v in failures.items()},'text_equal_cases':sum(r['same_text'] for r in rows),'tokens_equal_cases':sum(r['same_tokens'] for r in rows),'rows':rows}
    A=R/'analysis';A.mkdir(exist_ok=True);save(A/'paired-quality.json',out);save(A/'logits-selection.json',select_logits(rows,cases))
    with (A/'paired-cases.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['id','category','cpu_success','gpu_success','same_tokens','same_text','cpu_text','gpu_text','cpu_flags','gpu_flags'];w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in out.items() if k not in ['rows']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
