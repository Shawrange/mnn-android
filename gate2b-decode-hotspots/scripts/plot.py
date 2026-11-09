from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];s=json.loads((R/'analysis/summary.json').read_text())
cats=['MLP linear','QKV/O linear','Vocabulary head linear','Attention','Norm','Layout/Raster','Geometry While','Elementwise unary','Elementwise binary','Cast']
colors=['#2c6189','#3e8da2','#5db5ac','#d48742','#a77099','#89a555','#c2a05c','#8992b5','#a5baca','#b8b8b8']
fig,axes=plt.subplots(2,1,figsize=(11,6.5),layout='constrained')
for ax,key,title in [(axes[0],'share_op_percent','Share of callback-covered Decode wall time'),(axes[1],'share_native_percent','Accounting within profiled native Decode timer')]:
    left=[0.,0.]
    for c,color in zip(cats,colors):
        v=[s['categories'][str(t)][c][key]['mean'] if c in s['categories'][str(t)] else 0 for t in [64,256]]
        ax.barh([0,1],v,left=left,label=c,color=color)
        left=[a+b for a,b in zip(left,v)]
    if key=='share_native_percent':ax.barh([0,1],[100-a for a in left],left=left,color='#ededed',edgecolor='#888',label='Unassigned (includes observer work)')
    ax.set(yticks=[0,1],yticklabels=['128 + 64','128 + 256'],xlim=(0,100),xlabel='Percent / process mean',title=title);ax.invert_yaxis()
handles,labels=axes[1].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncols=3,fontsize=8)
fig.suptitle('MNN 3.6.2 / Qwen3-0.6B / Xiaomi 15 CPU4 / official --profile\nProfile-mode accounting only; not unprofiled execution-time percentages',fontsize=11)
fig.savefig(R/'analysis/hotspot-accounting.png',dpi=180);fig.savefig(R/'analysis/hotspot-accounting.svg')
