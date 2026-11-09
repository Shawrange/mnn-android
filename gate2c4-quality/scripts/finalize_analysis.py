from analyze import *
def main():
    check_freeze();A=R/'analysis';q=load(A/'paired-quality.json');diag=load(A/'logits-diagnostics.json')
    candidates=[p for p in sorted((R/'results').glob('gpu-evidence-*')) if load(p/'session-status.json')['status']=='completed'];assert candidates
    d=candidates[-1];p=d/'CL001-profile';result=load(p/'result.json');out=(p/'run.stdout.txt').read_text(encoding='utf-8');err=(p/'run.stderr.txt').read_text(encoding='utf-8')
    events=[{'us':int(us),'label':label.strip()} for us,label in re.findall(r'kernel time = (\d+)\s+us ([^\n\r]+)',out)]
    counts=collections.Counter(e['label'] for e in events);generated=result['generated_count'];decodes=generated-1 if result['stopped'] else generated
    assert result['runtime_ok'] and counts['Convolution0']==197*(1+decodes) and counts['flash_attention_prefill']==28 and counts['flash_decode_partial']==counts['flash_decode_reduce']==28*decodes
    fallbacks=[line for line in (out+err).splitlines() if "Don't support type" in line]
    assert not fallbacks
    build=R.parent/'gate2c-opencl/evidence/build/profile/ninja-commands.txt';assert '-DOPENCL_FALLBACK_LOG' in build.read_text(encoding='utf-8') and 'ENABLE_OPENCL_TIME_PROFILER' in build.read_text(encoding='utf-8')
    formal=R/q['formal_session'];assert load(p/'device/sample.input_ids.json')==load(formal/'CL001-opencl/device/sample.input_ids.json')
    assert load(p/'device/sample.output_ids.json')==load(formal/'CL001-opencl/device/sample.output_ids.json')
    gpu={'session':str(d.relative_to(R)),'case':'CL001','event_count':len(events),'event_counts':dict(counts),'fallback_log_lines':fallbacks,'nonzero_event_counts':dict(collections.Counter(x['label'] for x in events if x['us']>0)),'major_model_gpu_compute_proved':True,'profile_input_output_ids_match_clean_formal':True,'profile_library_sha256':sha(R.parent/'gate2c-opencl/staging/profile/libMNN.so'),'macro_evidence':str(build.relative_to(R.parent)),'macro_evidence_sha256':sha(build),'boundary':'Separate event diagnostic; proves major OpenCL model math, not all process work or all possible fallback absence; no diagnostic timing used for quality/performance comparison.'}
    save(A/'gpu-execution-evidence.json',gpu)
    examples=[('CL010','输出了多个类别；冻结规则要求唯一类别，因此两端均失败。'),('CL013','GPU唯一类别仍为错误的咨询；CPU也未给唯一类别，两端失败不能解释为GPU质量下降。'),('EX001','代码块内字段可读，但严格JSON接口拒绝Markdown代码块，主分保持失败。'),('EX006','除代码块外，地点还丢失了会议室后缀；格式失败之外存在字段内容风险。'),('EX022','CPU输出号码，GPU输出null；两端均因代码块失败，不能在事后去围栏后重算主分。'),('IN006','CPU保留首字母小写，GPU全大写；GPU单独正确，复跑确认。'),('QA022','CPU12正确，GPU24错误；可重复的个例下降，但不足以支持整体有意义下降。'),('QA023','CPU句子含东边但未遵守只输出方向；GPU东是预先列出的合法变体，主分有差异，不能称CPU事实知识错误。'),('QA011','CPU包含正确算式但多余解释，GPU25事实错误；双方主分均失败，原因不同。'),('QA003','公园后的句号导致精确格式失败；评分器content_error表示精确匹配失败，不必然是事实错误。')]
    rows={r['id']:r for r in q['rows']};review=[]
    for ident,note in examples:
        row=rows[ident];review.append({'id':ident,'reviewer':'Codex evidence inspection; not independent human review','cpu_text':row['cpu_text'],'gpu_text':row['gpu_text'],'cpu_success_unchanged':row['cpu_success'],'gpu_success_unchanged':row['gpu_success'],'note':note,'changed_primary_score':False})
    save(A/'review-records.json',{'scope':'Representative objective scoring audit; no subjective or post-hoc primary score changes','independent_human_review_performed':False,'records':review})
    repeats_ok=all(v[b]['same_output_ids_as_formal'] for v in diag['repeats'] for b in ['cpu','gpu'])
    decision=q['preliminary_decision']
    if decision=='A_pending_gpu_execution_evidence':decision='A'
    elif decision=='B_pending_repeats':decision='B' if repeats_ok else 'D'
    assert decision in ['A','B','C','D']
    final={'decision':decision,'enter_independent_gpu_performance_baseline':decision=='A','frozen_quality_protocol_satisfied_by_gpu':q['quality_gates']['opencl']['quality_gate_met'],'frozen_quality_protocol_satisfied_by_cpu':q['quality_gates']['cpu']['quality_gate_met'],'major_gpu_execution_proved':True,'repeated_discordance_outputs_identical':repeats_ok,'runtime_defect_claimed':False,'old_logits_threshold_failure_retained':True,'scope':'This fixed quantized asset + no-thinking fixed prompt/config + 100 authored short tasks; no claim all Qwen3-0.6B models or all prompts fail.','next_step':'Re-scope tasks or define a separate asset/prompt/postprocessing experiment with a new frozen dataset; no optimization/NPU/performance baseline now.'}
    save(A/'decision.json',final)
    print(json.dumps(final,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
