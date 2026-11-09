from analyze import *
import array
def floats(p):
    a=array.array('f');a.frombytes(p.read_bytes());return list(a)
def summarise(values,ref_ids):
    assert len(values)==151936 and all(math.isfinite(v) for v in values)
    top=sorted(range(len(values)),key=lambda i:(-values[i],i))[:5];mx=values[top[0]];den=math.fsum(math.exp(x-mx) for x in values)
    result={'top5':[{'id':i,'logit':values[i],'probability':math.exp(values[i]-mx)/den} for i in top],'top1_top2_margin':values[top[0]]-values[top[1]],'reference_next':None}
    if ref_ids is not None:
        token=ref_ids;value=values[token];rank=1+sum(v>value or (v==value and i<token) for i,v in enumerate(values));result['reference_next']={'id':token,'rank':rank,'logit':value,'probability':math.exp(value-mx)/den}
    return result
def main():
    check_freeze();q=load(R/'analysis/paired-quality.json');primary=R/q['formal_session'];dirs=[p for p in sorted((R/'results').glob('diagnostics-*')) if load(p/'session-status.json')['status']=='completed'];assert dirs;d=dirs[-1];selected=load(d/'selection.json');records=[];repeats=[]
    byid={x['id']:x for x in q['rows']}
    for s in selected:
        ident=s['id']
        for label,prefix in [('first-token',[]),('first-split',s['common_prefix_ids'])]:
            root=d/(ident+'-'+label);metas={};data={};ref={}
            for backend in ['cpu','opencl']:
                p=root/(ident+'-'+label+'-'+backend);files=p/'device';m=load(files/'sample.meta.json');ids=load(files/'sample.input_ids.json');prompts=load(files/'sample.prompt_ids.json')
                assert ids==prompts+prefix and m['initial_kv']==0 and m['kv_after']==len(ids) and m['generated_count']==0 and m['nonfinite']==0 and m['read_twice_identical'] and m['shape']==[1,1,151936]
                metas[backend]=m;data[backend]=floats(files/'sample.logits.f32');ref[backend]=load(files/'sample.reference_ids.json')
            assert ref['cpu']==ref['opencl']
            a=root/(ident+'-'+label+'-cpu')/'device/sample.input_ids.json';b=root/(ident+'-'+label+'-opencl')/'device/sample.input_ids.json';assert load(a)==load(b)
            refprefix_ok=all(metas[b]['reference_prompt_prefix_matches'] for b in metas) and ref['cpu'][:len(prefix)]==prefix
            nextref=ref['cpu'][len(prefix)] if refprefix_ok and len(ref['cpu'])>len(prefix) else None
            c=summarise(data['cpu'],nextref);g=summarise(data['opencl'],nextref)
            for backend,summary in [('cpu',c),('opencl',g)]:
                summary['top5_text']=metas[backend]['top5_text']
            original_cpu=s['original_cpu_next'] if label=='first-split' else byid[ident]['cpu_tokens'][0]
            original_gpu=s['original_gpu_next'] if label=='first-split' else byid[ident]['gpu_tokens'][0]
            cpu_top=c['top5'][0]['id'];gpu_top=g['top5'][0]['id'];
            records.append({'id':ident,'position':label,'common_output_prefix_len':len(prefix),'input_length':metas['cpu']['input_len'],'same_history_verified':True,'cpu_correct':s['cpu_success'],'gpu_correct':s['gpu_success'],'original_cpu_next':original_cpu,'original_gpu_next':original_gpu,'replay_cpu_matches_original':cpu_top==original_cpu,'replay_gpu_matches_original':gpu_top==original_gpu,'replay_top1_same':cpu_top==gpu_top,'both_margins_ge_1':c['top1_top2_margin']>=1 and g['top1_top2_margin']>=1,'reference_next_valid':nextref is not None,'reference_token_reason':'fixed gold prefix matches rendered-token history' if nextref is not None else 'reference answer does not share the current output prefix, or tokenization boundary mismatch/end','cpu':c,'gpu':g,'top5_overlap':len({x['id'] for x in c['top5']}&{x['id'] for x in g['top5']})})
        if s['cpu_success']!=s['gpu_success']:
            for rep in [1,2]:
                row={'id':ident,'repeat':rep}
                for backend,key in [('cpu','cpu'),('opencl','gpu')]:
                    p=d/f'repeat-{rep}'/(ident+f'-repeat{rep}-'+backend);result=load(p/'result.json');score=load(p/'score.json');ids=load(p/'device/sample.output_ids.json')
                    row[key]={'success':score['success'],'same_output_ids_as_formal':ids==byid[ident][key+'_tokens'],'text':result['raw_text'],'flags':score['flags']}
                repeats.append(row)
    A=R/'analysis';save(A/'logits-diagnostics.json',{'session':str(d.relative_to(R)),'selection':selected,'records':records,'repeats':repeats,'boundary':'Each value comes from a fresh full-Prefill of identical token history; not guaranteed to equal cached incremental Decode arithmetic.'})
    print(json.dumps({'selected_cases':len(selected),'replays':len(records),'discordance_repeats':len(repeats),'replay_original_mismatch_records':sum(not x['replay_cpu_matches_original'] or not x['replay_gpu_matches_original'] for x in records),'high_margin_divergence_records':sum(x['both_margins_ge_1'] and not x['replay_top1_same'] for x in records)},indent=2))
if __name__=='__main__':main()
