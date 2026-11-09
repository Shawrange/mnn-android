from run import *
import subprocess
assert not (R/'freeze.json').exists(),'Freeze is immutable; never replace after formal data collection'
cases=[json.loads(x) for x in (R/'datasets/formal.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(cases)==100 and len({x['id'] for x in cases})==100
for c in cases:
    sample={'raw_text':c['variants'][0],'status':1,'stopped':True,'runtime_ok':True,'process_exit':0}
    assert grade(c,sample)['success'],c['id']
pilot=sorted((R/'results').glob('pilot-*'))[-1];assert load(pilot/'session-status.json')['status']=='completed'
p=subprocess.run(['python','-B',str(R/'scripts/test_score.py')],capture_output=True)
(R/'evidence/scorer-tests.stdout.txt').write_bytes(p.stdout);(R/'evidence/scorer-tests.stderr.txt').write_bytes(p.stderr);assert p.returncode==0
files=['datasets/formal.jsonl','datasets/pilot.jsonl','protocol.md','configs/runtime.json','scripts/score.py','scripts/test_score.py','scripts/quality_probe.cpp','scripts/run.py','scripts/make_formal.py','staging/quality_probe']
snapshot={'frozen_at_utc':utc(),'formal_case_count':100,'per_category':25,'pilot_separate':True,'pilot_session':str(pilot.relative_to(R)),'scorer_tests_exit_code':p.returncode,'sha256':{name:sha(R/name) for name in files},'thresholds':{'classification_min':23,'extraction_min':22,'instruction_min':23,'qa_min':23,'overall_min':92,'extraction_format_min':24,'natural_eos_min':99,'runtime_errors_max':0,'gpu_minus_cpu_min':-.04,'per_category_delta_min':-.08,'cpu_only_max':5,'paired_CI_lower_min':-.10}}
save(R/'freeze.json',snapshot);print('Frozen 100 cases, scoring, settings, driver and protocol at',snapshot['frozen_at_utc'])
