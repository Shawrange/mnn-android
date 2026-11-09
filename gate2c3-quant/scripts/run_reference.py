from pathlib import Path
import subprocess,json,shutil,sys
R=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8')
source=R.parent/'gate2c2-numerics/results/checkpoints-20261108T202929Z-254d02'
for kind,n in [('synthetic',8),('natural',13)]:
    dest=R/'evidence/inputs'/kind;dest.mkdir(parents=True,exist_ok=True)
    for name,old in [('x.f32','sample.r0.q_input.f32'),('ids.json','sample.ids.json'),('meta.json','sample.r0.meta.json')]:shutil.copyfile(source/f'cpu-low-{kind}-checkpoints-p0/out'/old,dest/name)
    out=R/'references'/kind;out.mkdir(parents=True,exist_ok=True)
    root='/mnt/e/DUANCE/gate2c3-quant'
    cmd=['wsl','-d','Ubuntu','--',root+'/staging/reference',root+f'/evidence/inputs/{kind}/x.f32',root+'/evidence/weight/q.decoded.i8',root+'/evidence/weight/q.alpha.f32',root+'/evidence/weight/q.bias.f32',root+f'/references/{kind}/reference',str(n)]
    p=subprocess.run(cmd,capture_output=True);(out/'stdout.txt').write_bytes(p.stdout);(out/'stderr.txt').write_bytes(p.stderr);(out/'command.json').write_text(json.dumps({'command':cmd,'exit_code':p.returncode},indent=2))
    assert p.returncode==0;print('Independent references computed:',kind)
