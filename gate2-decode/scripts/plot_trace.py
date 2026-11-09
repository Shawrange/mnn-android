from pathlib import Path
import csv,json,statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];summary=json.loads((R/'analysis/summary.json').read_text())
runs=[]
for session in summary['sessions']:
    for p in (R/session).glob('*-on-tg256'):
        if json.loads((p/'sample.json').read_text())['status']!='success':continue
        rows=list(csv.DictReader((p/'trace.steps.csv').open()));response=max(int(r['response']) for r in rows)
        runs.append([{k:int(v) for k,v in r.items()} for r in rows if int(r['response'])==response])
rows=[]
for i in range(256):
    d={'token':i+1,'kv_after':129+i,'runs':len(runs)}
    for key in ['wall_ns','attention_ns','realloc_ns']:
        v=[r[i][key]/1e6 for r in runs]
        for name,fn in [('mean',st.mean),('median',st.median),('min',min),('max',max)]:d[key.replace('_ns','_ms')+'_'+name]=fn(v)
    rows.append(d)
out=R/'analysis'
with (out/'token-aggregates.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
fig,axes=plt.subplots(2,1,figsize=(10,6.5),sharex=True,layout='constrained')
for ax,key,title in zip(axes,['wall_ms','attention_ms'],['Decode step (native-like boundary)','Attention onExecute (includes KV management)']):
    x=[r['token'] for r in rows]
    ax.fill_between(x,[r[key+'_min'] for r in rows],[r[key+'_max'] for r in rows],alpha=.18,color='#276b9d',label='Observed min-max across runs')
    ax.plot(x,[r[key+'_median'] for r in rows],color='#276b9d',lw=1.2,label='Per-position median')
    for t in [65,130,195]:ax.axvline(t,color='#ba5b35',ls='--',lw=.8)
    ax.set(title=title,ylabel='Wall time / ms');ax.grid(alpha=.2);ax.set_xlim(1,256)
    ax.legend(loc='upper left',fontsize=8)
axes[1].set_xlabel('Generated token / forward step (KV after = 128 + step)')
fig.suptitle(f'Qwen3-0.6B / MNN 3.6.2 / Xiaomi 15 CPU4 / trace-on n={len(runs)}\nDashed lines: observed capacity growth, not OS allocation count',fontsize=11)
fig.savefig(out/'decode-trace.png',dpi=180);fig.savefig(out/'decode-trace.svg')
(out/'plot-environment.json').write_text(json.dumps({'matplotlib':matplotlib.__version__,'n_runs':len(runs)},indent=2))
