from pathlib import Path
import csv,hashlib,json,math,statistics
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT.parent/'mobile-llm-runtime-lab'
out=ROOT/'evidence/gate1-audit';out.mkdir(parents=True,exist_ok=True)
session=LAB/'results/baseline-20261108T140723-9efc5f25'
rows=[];hashes={}
for path in sorted(session.glob('*/sample.json')):
    d=json.loads(path.read_text(encoding='utf-8'))
    raw=json.loads((path.parent/'benchmark.json').read_text())
    assert d['status']=='success' and d['exit_code']==0
    assert d['decode_tps']==raw['results'][0]['decode_tps']
    d['sample_path']=str(path.relative_to(LAB))
    for f in path.parent.iterdir():
        if f.is_file():hashes[str(f.relative_to(LAB))]=hashlib.sha256(f.read_bytes()).hexdigest()
    rows.append(d)
csvpath=LAB/'analysis/baseline-20261108T143156-8442118b/samples.csv'
with csvpath.open(encoding='utf-8-sig') as f:csvrows=list(csv.DictReader(f))
assert len(csvrows)==len(rows)==50
for row in csvrows:
    d=next(x for x in rows if x['sample_path']==row['sample_path'])
    assert float(row['decode_tps'])==d['decode_tps']
pairs=[]
for block in range(1,11):
    a=next(x for x in rows if x['round']==block and x['prompt_tokens']==128 and x['generated_tokens']==64)
    b=next(x for x in rows if x['round']==block and x['prompt_tokens']==128 and x['generated_tokens']==256)
    pairs.append({'block':block,'short_index':a['index'],'long_index':b['index'],'short_tps':a['decode_tps'],'long_tps':b['decode_tps'],
                  'long_minus_short_percent':100*(b['decode_tps']/a['decode_tps']-1),'short_before_long':a['index']<b['index'],
                  'short_before_skin':a['before']['skin_c'],'long_before_skin':b['before']['skin_c'],
                  'short_after_skin':a['after']['skin_c'],'long_after_skin':b['after']['skin_c'],
                  'short_before_cpu_max':a['before']['cpu_max_c'],'long_before_cpu_max':b['before']['cpu_max_c'],
                  'short_path':a['sample_path'],'long_path':b['sample_path']})
neg=sum(p['long_minus_short_percent']<0 for p in pairs)
sign_p=min(1,2*sum(math.comb(10,k) for k in range(min(neg,10-neg)+1))/2**10)
summary={'pairs':pairs,'long_slower_blocks':neg,'pair_count':10,'median_paired_change_percent':statistics.median(p['long_minus_short_percent'] for p in pairs),
         'short_first_blocks':sum(p['short_before_long'] for p in pairs),'two_sided_sign_test_p_exploratory':sign_p,
         'limits':['Paired signs are repeatability evidence, not causal identification','Temperature/frequency endpoint and whole-process switches are not decode-phase traces','Same effective dynamic_option=0 for both workloads','Sign test assumes independent/exchangeable block signs; temporal dependence and one-device sampling limit inference']}
(out/'paired-review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (out/'paired-review.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=pairs[0]);w.writeheader();w.writerows(pairs)
for path in LAB.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts:
        hashes[str(path.relative_to(LAB))]=hashlib.sha256(path.read_bytes()).hexdigest()
(out/'gate1-preservation-hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
