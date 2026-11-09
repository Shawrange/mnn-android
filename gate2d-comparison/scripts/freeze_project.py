"""Finalize once all planned experiments and evidence audits are complete."""
from run import *
P=R.parent
assert not (P/'PROJECT_FREEZE.json').exists(),'Final freeze marker may not be overwritten'
v=load(R/'verification-summary.json');assert v['formal_successful']==36 and not v['prior_changed_files']
assert load(R/'evidence/final-device-check/verified.json')['all_original_assets_unchanged']
for n in ['README.md','FINAL_TECHNICAL_REPORT.md','INTERVIEW_GUIDE.md','RESUME_PROJECT.md']:assert (P/n).is_file()
checks={'mnn_commit':C['mnn_commit'],'model_revision':C['model_revision'],'gate2d_formal_runs':36,'gate2d_clean_cpu_gpu_runs_completed':True,'prior_evidence_unchanged':True,'runtime_optimization_implemented':False,'upstream_pr_claimed':False,'npu_executed':False,'fixed_application_quality_passed':False,'product_performance_acceptance_claimed':False,'further_inference_planned':False}
save(R/'analysis/final-acceptance.json',checks)
items={}
for p in sorted(P.rglob('*')):
    if not p.is_file() or p.name in ['PROJECT_FREEZE.json','project-manifest.json']:continue
    if any(x in p.parts for x in ['.git','.agents','.codex','.aws']):continue
    items[p.relative_to(P).as_posix()]=sha(p)
save(P/'project-manifest.json',{'algorithm':'sha256','excludes':['project-manifest.json','PROJECT_FREEZE.json','.git','.agents','.codex','.aws'],'sha256':items})
save(P/'PROJECT_FREEZE.json',{'status':'frozen','frozen_at_utc':utc(),'mnn_commit':C['mnn_commit'],'model_revision':C['model_revision'],'formal_gate2d_processes':36,'project_manifest_sha256':sha(P/'project-manifest.json'),'files_hashed':len(items),'final_decision':'OpenCL Prefill scope cheaper; CPU Decode scope cheaper in this fixed experiment. Fixed application quality failed. No Runtime optimization warranted. End project.','no_further_experiments_in_this_project':True,'reproduction_policy':'Read-only offline verification allowed. Re-execution requires a separate copy/session and must not alter this archive.','acceptance':checks})
print('Project formally frozen:',len(items),'files; manifest SHA256',sha(P/'project-manifest.json'))
