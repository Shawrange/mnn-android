"""One bounded CLI metadata-path correction, retaining all first-pilot evidence."""
from run import *
dep=load(R/'deployment.json');d=R/'evidence/path-compatibility';d.mkdir();r=Runner(C,d)
for b in ['cpu','opencl']:
    must(r.shell('weight-link-'+b,'ln -s '+MODEL+'/llm.mnn.weight '+dep['remote']+'/'+b+'/llm.mnn.weight',d)[2])
p=sorted((R/'results').glob('pilot-*'))[0]
save(d/'pilot-review.json',{'session':str(p.relative_to(R)),'valid_for_comparison':False,'reason':'Native CLI getDirectoryOf requires slash in config path and a colocated weight reference; first pilot reports impossible modelSize. Raw records retained, not formal samples.','fixed_by':'./config.json and symlink to unchanged original weight','runtime_source_changed':False,'at_utc':utc()})
