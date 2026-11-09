from pathlib import Path
import re,json,csv,collections,hashlib
R=Path(__file__).resolve().parents[1];A=R/'analysis';A.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
smokes=[]
for phase in ['clean','profile']:
    for d in sorted((R/'results').glob(phase+'-*')):
        out=(d/'demo.stdout.txt').read_text(encoding='utf-8');err=(d/'demo.stderr.txt').read_text(encoding='utf-8');cmd=load(d/'demo.command.json')
        tokens=re.search(r'decode tokens num\s*=\s*(\d+)',out)
        bad=bool(re.search(r'LLM init error|\[Error\]|Unable to open|Build program failed|CANNOT LINK',out+err))
        success=cmd['exit_code']==0 and not bad and tokens is not None and int(tokens.group(1))>0
        row={'path':str(d.relative_to(R)),'kind':phase,'exit_code':cmd['exit_code'],'semantic_success':success,'generated_tokens':int(tokens.group(1)) if tokens else None,'failure_layer':'deployment configuration path (base_dir concatenation)' if not success and 'tokenizer file not found' in out else None}
        events=[{'us':int(us),'label':label.strip()} for us,label in re.findall(r'kernel time = (\d+)\s+us ([^\n\r]+)',out)]
        fallback=[line for line in (out+err).splitlines() if "Don't support type" in line]
        row.update(kernel_events=len(events),event_label_counts=dict(collections.Counter(x['label'] for x in events)),fallback_log_lines=fallback)
        if phase=='profile' and success:
            assert row['event_label_counts']['Convolution0']==197*(1+row['generated_tokens'])
            assert row['event_label_counts']['flash_decode_partial']==28*row['generated_tokens']
            assert row['event_label_counts']['flash_decode_reduce']==28*row['generated_tokens']
            assert row['event_label_counts']['flash_attention_prefill']==28
            row['major_model_gpu_execution_proved']=True
            with (A/'gpu-event-counts.csv').open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f);w.writerow(['label','count','nonzero_events']);w.writerows((label,count,sum(x['label']==label and x['us']>0 for x in events)) for label,count in sorted(row['event_label_counts'].items()))
        save(d/'runtime-analysis.json',row);smokes.append(row)
probe=load(next((R/'results').glob('probe-*/capability-summary.json')))
properties=list(csv.DictReader((R/'evidence/npu-static/model-properties.tsv').open(),delimiter='\t'))
convs=[r for r in properties if r['type']=='Convolution'];attn=[r for r in properties if r['type']=='Attention']
npu={'convolutions':len(convs),'weight_bits':dict(collections.Counter(r['weight_bits'] for r in convs)),'loader_asymmetric_convolutions':sum(r['loader_asymmetric']=='1' for r in convs),'attentions':len(attn),'attention_output_c4':dict(collections.Counter(r['output_c4'] for r in attn)),'sdk_state':load(R/'evidence/npu-static/sdk-state.json'),'runtime_tested':False,'compatibility':'Does not match documented recommended Hexagon LLM export; source supports additional quant branches, so no blanket unsupported claim without runtime/layout validation. QNN unconverted and untested.'}
logits=load(A/'logits-comparison.json')
result={'standalone_opencl_probes':probe,'smokes':smokes,'numerical_prefill_probes':logits,'npu_static':npu,'decision':{'device_opencl_usable':all(p['arithmetic_kernel_passed'] for p in probe['probes']),'clean_llm_execution_smoke':any(s['kind']=='clean' and s['semantic_success'] for s in smokes),'actual_major_gpu_kernels_proved':any(s.get('major_model_gpu_execution_proved') for s in smokes),'all_prefill_numeric_screening_passed':all(x['screening_passed'] for x in logits),'next_step':'GPU numerical correctness and path investigation first; independent GPU performance baseline deferred; no optimization or NPU runtime tests.'}}
save(A/'summary.json',result);print(json.dumps(result['decision'],ensure_ascii=False,indent=2))
