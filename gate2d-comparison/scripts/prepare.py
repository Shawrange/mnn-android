"""Protect earlier evidence and prepare isolated clean binaries; never overwrites."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
assert not (R/'evidence/prior-hashes.json').exists()
old=['gate0','mobile-llm-runtime-lab','gate2-decode','gate2b-decode-hotspots','gate2c-opencl','gate2c2-numerics','gate2c3-quant','gate2c4-quality']
prior={str(p.relative_to(R.parent)):sha(p) for n in old for p in (R.parent/n).rglob('*') if p.is_file()}
save(R/'evidence/prior-hashes.json',prior)
for b,s in [('cpu','gate0/staging'),('opencl','gate2c-opencl/staging/clean')]:
    d=R/'staging'/b;d.mkdir(exist_ok=False)
    for name in ['libMNN.so','llm_bench']:shutil.copyfile(R.parent/s/name,d/name)
    cfg=json.loads((R.parent/'gate0/assets/Qwen3-0.6B-MNN/config.cpu.json').read_text())
    cfg.update(base_dir='/data/local/tmp/mnn-gate0-20261108T134731469951Z/Qwen3-0.6B-MNN/',backend_type=b,tokenizer_file='tokenizer.txt',power='normal',ignore_eos=True,async_=False)
    cfg.pop('async_',None);cfg.update({'async':False,'dynamic_option':0,'attention_mode':8,'use_mmap':False,'tmp_path':'tmp','cpu_sme2_neon_division_ratio':41})
    save(R/'configs'/f'{b}.json',cfg)
save(R/'evidence/archived-artifact-hashes.json',{str(p.relative_to(R)):sha(p) for p in (R/'staging').rglob('*') if p.is_file()})
print('Protected',len(prior),'old files; staged clean archived binaries')
