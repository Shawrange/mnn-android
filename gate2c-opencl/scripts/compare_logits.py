from pathlib import Path
import array,json,math,hashlib
R=Path(__file__).resolve().parents[1]
out=R/'analysis';out.mkdir(exist_ok=True);data=[]
for session in sorted((R/'results').glob('logits-*')):
    if json.loads((session/'session-status.json').read_text())['status']!='completed':continue
    for kind in ['synthetic','natural']:
        a=session/('cpu-'+kind);b=session/('opencl-'+kind)
        cpu=array.array('f');gpu=array.array('f');cpu.frombytes((a/'logits.f32').read_bytes());gpu.frombytes((b/'logits.f32').read_bytes())
        ids_equal=(a/'ids.txt').read_bytes()==(b/'ids.txt').read_bytes();shape_equal=(a/'meta.txt').read_text().split('shape=')[1]==(b/'meta.txt').read_text().split('shape=')[1]
        assert len(cpu)==len(gpu) and len(cpu)>=151936
        finite=all(math.isfinite(x) for v in [cpu,gpu] for x in v)
        dif=[abs(x-y) for x,y in zip(cpu,gpu)];aa=sum(x*x for x in cpu);bb=sum(x*x for x in gpu)
        nrmse=math.sqrt(sum(d*d for d in dif)/aa);cosine=sum(x*y for x,y in zip(cpu,gpu))/math.sqrt(aa*bb)
        fraction=sum(d<=.1+.02*abs(x) for x,d in zip(cpu,dif))/len(cpu)
        topcpu=sorted(range(len(cpu)),key=lambda i:cpu[i],reverse=True)[:5];topgpu=sorted(range(len(gpu)),key=lambda i:gpu[i],reverse=True)[:5]
        passed=ids_equal and shape_equal and finite and nrmse<=.02 and cosine>=.999 and fraction>=.999
        data.append({'session':str(session.relative_to(R)),'kind':kind,'elements':len(cpu),'ids_equal':ids_equal,'shape_equal':shape_equal,'finite':finite,'relative_rmse':nrmse,'cosine':cosine,'abs_rel_bound_fraction':fraction,'max_abs_error':max(dif),'mean_abs_error':sum(dif)/len(dif),'cpu_top5':topcpu,'gpu_top5':topgpu,'top5_overlap':len(set(topcpu)&set(topgpu)),'cpu_top1_top2_margin':cpu[topcpu[0]]-cpu[topcpu[1]],'top1_equal':topcpu[0]==topgpu[0],'screening_passed':passed,'thresholds':{'relative_rmse_max':.02,'cosine_min':.999,'abs':.1,'rel':.02,'element_fraction_min':.999}})
(out/'logits-comparison.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data,ensure_ascii=False,indent=2))
