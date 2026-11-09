from pathlib import Path
import csv,hashlib,json,subprocess,sys,re,collections
R=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def command(args):
    p=subprocess.run(args,capture_output=True);return {'command':args,'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8',errors='replace'),'stderr':p.stderr.decode('utf-8',errors='replace')}
old=load(R/'evidence/prior-stage-hashes.json');changed=[p for p,h in old.items() if not (R.parent/p).is_file() or sha(R.parent/p)!=h]
checks={'prior_files_checked':len(old),'prior_changed_files':changed};commands=[]
for label,args in [('clean-head',['git','-C','/home/shawrange/src/MNN-3.6.2','rev-parse','HEAD']),('clean-status',['git','-C','/home/shawrange/src/MNN-3.6.2','status','--porcelain','--untracked-files=no'])]:
    c=command(['wsl','-d','Ubuntu','--',*args]);commands.append(c);checks[label]=c['exit_code']==0 and (c['stdout'].strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d' if label=='clean-head' else not c['stdout'].strip())
p=subprocess.run(['wsl','-d','Ubuntu','--','git','-C','/home/shawrange/src/MNN-decode-gate2a','diff','--binary'],capture_output=True)
checks['gate2a_live_patch_unchanged']=p.returncode==0 and p.stdout==(R.parent/'gate2-decode/evidence/diagnostic.patch').read_bytes()
checks['source_snapshots_valid']=all(sha(R/'evidence/source'/x['file'])==x['sha256'] for x in load(R/'evidence/source/manifest.json'))
checks['probe_build_exit_zero']=(R/'evidence/build/probe.exit.txt').read_text().strip()=='0'
checks['graph_verified_flatbuffer']=(R/'evidence/model/inspect.exit.txt').read_text().strip()=='0'
summaries=[load(p) for p in (R/'results').glob('correctness-*/correctness-summary.json')]
assert len(summaries)==1
expected=load(next((R.parent/'gate2-decode/results').glob('correctness-*/correctness-summary.json')))
checks['correctness_equal_and_matches_gate2a']=all(summaries[0][k]['equal_tokens_text_and_final_state'] and summaries[0][k]['tokens_sha256']==expected[k]['tokens_sha256'] for k in ['synthetic','natural'])
counts={};trace_calls=0;prof_names=0
for phase in ['pilot','official','detail']:
    data=[]
    for session in (R/'results').glob(phase+'-*'):
        assert load(session/'session-status.json')['status']=='completed'
        for p in session.glob('*/sample.json'):
            s=load(p);assert s['status']=='success' and s['exit_code']==0;data.append(s)
            if s['tool']=='official':
                raw=load(p.parent/'benchmark.json');assert raw['results'][0]['decode_tps']==s['decode_tps']
                if s['mode']=='profile':
                    profile=load(p.parent/'profile.json');rr=[x for x in profile if x['phase']=='decode' and x['name']=='*'];assert sum(x['calls'] for x in rr)==1188*s['tg']
                    assert next(x for x in rr if x['type']=='Convolution')['calls']==197*s['tg'];assert next(x for x in rr if x['type']=='Attention')['calls']==28*s['tg']
                    nn=[x for x in profile if x['phase']=='decode' and x['name']!='*'];assert len(nn)==1188;prof_names+=len(nn)
                    assert abs(sum(x['total_us'] for x in rr)-sum(x['total_us'] for x in nn))<3
            elif s['mode']=='detail':
                sm=s['probe_summary'];assert sm['nested']==sm['foreign']==sm['dropped']==sm['new_metadata_measured']==0
                meta={int(x['id']):x for x in csv.DictReader((p.parent/'ops.tsv').open(),delimiter='\t')};calls=list(csv.DictReader((p.parent/'calls.csv').open()));assert len(calls)==sm['records']
                decode=[x for x in calls if int(x['token'])>0];assert len(decode)==1188*s['tg'];trace_calls+=len(decode)
                pertoken=collections.Counter(int(x['token']) for x in decode)
                attn=collections.Counter(int(x['token']) for x in decode if meta[int(x['op'])]['type']=='Attention')
                assert set(pertoken)==set(range(1,s['tg']+1))
                assert all(pertoken[t]==1188 and attn[t]==28 for t in pertoken)
                assert all(int(x['ns'])>=0 for x in calls)
                assert all(int(a['start_ns'])+int(a['ns'])<=int(b['start_ns']) for a,b in zip(calls,calls[1:]))
    counts[phase]=len(data)
checks['sample_counts']=counts;checks['formal_counts_valid']=counts=={'pilot':2,'official':24,'detail':8};checks['validated_detail_decode_calls']=trace_calls
checks['retained_failed_correctness_sessions']=sum(load(p)['status']=='failed' for p in (R/'results').glob('correctness-*/session-status.json'))
assert load(R/'analysis/summary.json')['successful']==32
adb=r'C:\Users\12761\AppData\Local\Android\Sdk\platform-tools\adb.exe';remote='/data/local/tmp/mnn-gate2b-20261108'
paths={remote+'/llm_bench':R.parent/'gate0/staging/llm_bench',remote+'/libMNN.so':R.parent/'gate0/staging/libMNN.so',remote+'/op_probe':R/'staging/op_probe'}
for n in ['llm.mnn','llm.mnn.weight','config.cpu.json','llm_config.json','tokenizer.txt']:paths['/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN/'+n]=R.parent/'gate0/assets/Qwen3-0.6B-MNN'/n
c=command([adb,'-s','ee19377b','shell','sha256sum '+' '.join(paths)]);commands.append(c);got={line.split()[1]:line.split()[0] for line in c['stdout'].splitlines() if len(line.split())==2}
checks['final_phone_assets_match']=c['exit_code']==0 and all(got.get(p)==sha(f) for p,f in paths.items())
checks['artifact_hashes']={p.name:sha(p) for p in (R/'staging').iterdir() if p.is_file()}
graph=list(csv.DictReader((R/'evidence/model/graph-detailed.tsv').open(),delimiter='\t'));nodes={x['name']:x for x in graph}
convs=[x for x in graph if x['type']=='Convolution'];bits=collections.Counter(int(x['aMaxOrBits']) for x in convs)
assert bits=={4:196,8:1} and all(x['kx']==x['ky']=='1' for x in convs)
for i in range(28):
    assert len(set(nodes[f'/layers.{i}/self_attn/{q}_proj/Linear']['input_indices'] for q in ['q','k','v']))==1
    assert len(set(nodes[f'/layers.{i}/mlp/{q}_proj/Linear']['input_indices'] for q in ['gate','up']))==1
checks['model_graph_invariants']={'convolution_nodes':len(convs),'weight_bits_counts':dict(bits),'all_28_layers_share_qkv_and_gate_up_input_indices':True}
mdchecks=[]
for p in R.glob('*.md'):
    t=p.read_text(encoding='utf-8');assert t.count('```')%2==0,p
    for link in re.findall(r'\]\(([^)]+)\)',t):
        if not link.startswith(('http','/')):assert (p.parent/link).exists(),(p,link)
    mdchecks.append(p.name)
checks['markdown_checked']=mdchecks
checks['passed']=not changed and all(checks[k] for k in ['clean-head','clean-status','gate2a_live_patch_unchanged','source_snapshots_valid','probe_build_exit_zero','graph_verified_flatbuffer','correctness_equal_and_matches_gate2a','formal_counts_valid','final_phone_assets_match'])
(R/'evidence/final-check-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'verification-summary.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='artifact-manifest.sha256.json' and '__pycache__' not in p.parts}
(R/'artifact-manifest.sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2));sys.exit(0 if checks['passed'] else 1)
