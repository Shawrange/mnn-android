"""Frozen deterministic scoring for short, objectively specified responses."""
import json
def no_duplicates(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('duplicate JSON key')
        out[k]=v
    return out
def grade(case,run):
    text=run.get('raw_text','');s=text.strip();flags=[]
    if run.get('process_exit',0)!=0 or run.get('status') in [4,5,-1] or not run.get('runtime_ok',True):flags.append('runtime_error')
    if run.get('status')==2:flags.append('truncated')
    if not run.get('stopped',False):flags.append('unfinished')
    if not s:flags.append('empty_output')
    answer_ok=False;format_ok=True;parsed=None
    if case['rule']=='json_exact':
        try:
            parsed=json.loads(s,object_pairs_hook=no_duplicates)
        except (ValueError,TypeError):flags.append('parse_failure');format_ok=False
        if format_ok:
            gold=case['gold'];format_ok=isinstance(parsed,dict) and set(parsed)==set(gold)
            if format_ok:format_ok=all(type(parsed[k]) is type(v) for k,v in gold.items())
            if not format_ok:flags.append('schema_error')
            else:answer_ok=parsed==gold
    else:
        answer_ok=s in case['variants']
        if case['category']=='classification':format_ok=s in ['咨询','投诉','表扬']
        else:format_ok=not any(t in s for t in ['```','<think>','</think>']) and '\n' not in s
        if not format_ok:flags.append('format_error')
    if not answer_ok and format_ok:flags.append('content_error')
    success=bool(answer_ok and not any(f in flags for f in ['runtime_error','truncated','unfinished','empty_output','parse_failure','schema_error','format_error']))
    return {'id':case['id'],'category':case['category'],'success':success,'answer_matches':answer_ok,'format_valid':format_ok,'flags':flags,'normalized_text':s,'parsed_json':parsed}
