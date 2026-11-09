from pathlib import Path
import json,re,csv,statistics as st
R=Path(__file__).resolve().parents[1];L=R.parent/'mobile-llm-runtime-lab'
audit=json.loads((R/'evidence/gate1-audit/paired-review.json').read_text())
rows=[]
for pair in audit['pairs']:
    for mode in ['short','long']:
        p=L/pair[mode+'_path'];s=json.loads(p.read_text());raw=(p.parent/'benchmark.stderr.txt').read_text()
        d={'block':pair['block'],'mode':mode,'tps':s['decode_tps'],'skin_before':s['before']['skin_c'],'skin_after':s['after']['skin_c'],'cpu_before':s['before']['cpu_max_c'],'cpu_after':s['after']['cpu_max_c']}
        for label,key in [('voluntary','Voluntary context switches'),('involuntary','Involuntary context switches')]:
            match=re.search(key+r':\s*(\d+)',raw);d[label]=int(match.group(1)) if match else None
        for when in ['before','after']:
            for policy in ['policy0','policy6']:
                for key in ['scaling_cur_freq','scaling_max_freq']:d[f'{when}_{policy}_{key}']=int(s[when]['policies'][policy][key])
        rows.append(d)
with (R/'evidence/gate1-audit/paired-states.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
summary={}
for m in ['short','long']:
    rr=[r for r in rows if r['mode']==m]
    summary[m]={key:{'median':st.median(r[key] for r in rr),'min':min(r[key] for r in rr),'max':max(r[key] for r in rr)} for key in ['voluntary','involuntary']}
summary['long_started_cooler_skin_blocks']=[p['block'] for p in audit['pairs'] if p['long_before_skin']<p['short_before_skin']]
summary['limits']='Whole-process switches include initialization/tuning/warmup; long process duration is greater. No decode-only scheduling measurement exists in Gate1. Endpoint frequencies are not residency or effective frequency.'
(R/'evidence/gate1-audit/state-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
