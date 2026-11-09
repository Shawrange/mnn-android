from pathlib import Path
import csv,json,hashlib,re
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
checks=[];sample_count=0
for p in sorted((R/'results').glob('control-*/*/sample.json')):
    s=load(p);raw=load(p.parent/'benchmark.json');assert s['status']=='success' and s['exit_code']==0
    assert s['decode_tps']==raw['results'][0]['decode_tps'] and s['prefill_tps']==raw['results'][0]['prefill_tps']
    sample_count+=1
    if s['mode']!='on':continue
    rr=list(csv.DictReader((p.parent/'trace.steps.csv').open()))
    ge=list(csv.DictReader((p.parent/'trace.growth.csv').open()))
    tokens=[]
    for response in [1,2]:
        rows=[{k:int(v) for k,v in r.items()} for r in rr if int(r['response'])==response]
        assert len(rows)==s['tg']
        tokens.append([r['token_id'] for r in rows])
        assert all(rows[i]['start_ns']+rows[i]['wall_ns']<=rows[i+1]['start_ns'] for i in range(len(rows)-1))
        for i,r in enumerate(rows,1):
            assert (r['token'],r['kv_before'],r['kv_after'],r['attention_count'],r['kv_count'])==(i,127+i,128+i,28,28)
            assert r['alloc_ns']==0 and r['attention_ns']>=r['realloc_ns']+r['update_ns']
        events=[{k:int(v) for k,v in g.items()} for g in ge if int(g['response'])==response]
        assert len(events)==(84 if s['tg']==256 else 0)
        for token,before,after in [(65,192,257),(130,257,322),(195,322,387)]:
            ev=[e for e in events if e['token']==token]
            if s['tg']==64:assert not ev;continue
            assert len(ev)==28 and len(set(e['manager'] for e in ev))==28
            assert all((e['capacity_before'],e['capacity_after'],e['past_before'],e['in_disk'])==(before,after,127+token,0) for e in ev)
    assert tokens[0]==tokens[1],'Warmup/measured token IDs differ'
    checks.append(str(p.parent.relative_to(R)))
assert sample_count==36 and len(checks)==12
for p in (R/'results').glob('correctness-*/correctness-summary.json'):
    for kind in ['synthetic','natural']:
        for suffix in ['tokens.txt','text.txt','meta.txt']:
            values=[(p.parent/(kind+'-'+mode)/suffix).read_bytes() for mode in ['clean','off','on']]
            assert values[0]==values[1]==values[2]
        assert len((p.parent/(kind+'-clean')/'tokens.txt').read_text().splitlines())==256
for p in R.glob('*.md'):
    text=p.read_text(encoding='utf-8');assert text.count('```')%2==0,p
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith(('http','/')):continue
        assert (p.parent/target).exists(),(p,target)
result={'samples_validated':sample_count,'trace_runs_validated':len(checks),'warmup_measured_tokens_equal':True,'actual_growth_capacity_past_and_manager_counts_validated':True,'correctness_rechecked':True,'markdown_local_links_and_fences_checked':True,'passed':True}
(R/'evidence/independent-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
