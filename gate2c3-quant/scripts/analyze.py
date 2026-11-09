from pathlib import Path
import json,numpy as np,hashlib,csv,re
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tsv(p):return {x.split('\t',1)[0]:x.split('\t',1)[1] for x in p.read_text().splitlines()}
def read(p,dtype):return np.fromfile(p,dtype=dtype)
def metric(a,b):
    assert a.shape==b.shape
    a=a.astype('f8');b=b.astype('f8');err=np.abs(b-a);diff=b-a
    return dict(elements=a.size,all_finite=bool(np.isfinite(a).all() and np.isfinite(b).all()),relative_rmse=float(np.linalg.norm(diff)/np.linalg.norm(a)),cosine=float(np.dot(a.ravel(),b.ravel())/(np.linalg.norm(a)*np.linalg.norm(b))),max_abs=float(err.max()),mean_abs=float(err.mean()),min_delta=float(diff.min()),max_delta=float(diff.max()),a_min=float(a.min()),a_max=float(a.max()),b_min=float(b.min()),b_max=float(b.max()),exact_elements=int(np.count_nonzero(a==b)),p50_abs=float(np.median(err)),p99_abs=float(np.quantile(err,.99)))
def main():
    sessions=[p for p in sorted((R/'results').glob('q-only-*')) if load(p/'session-status.json')['status']=='completed'];assert sessions
    d=sessions[-1];(R/'analysis').mkdir(exist_ok=True);checks=[];metrics=[];timings=[];functions=[]
    weight=R/'evidence/weight';alpha=read(weight/'q.alpha.f32','<f4').reshape(2048,16,2);wi=read(weight/'q.decoded.i8','i1').reshape(2048,1024)
    raw=(weight/'q.raw_weight.bin').read_bytes();packed=raw[22:]
    linkmap=(R/'evidence/build/libMNN.map').read_text()
    for kind,n in [('synthetic',8),('natural',13)]:
        x=read(R/f'evidence/inputs/{kind}/x.f32','<f4').reshape(n,1024)
        base=d/f'{kind}-diag-on/out';ref=R/'references'/kind
        loadmeta=tsv(base/'trace.load.meta.tsv')
        assert loadmeta['alphaIsFp16']=='0' and loadmeta['blockNum']=='16' and loadmeta['canUseInt4']=='1'
        assert (base/'trace.load.decoded_weight.bin').read_bytes()==packed
        assert (base/'trace.load.alpha.bin').read_bytes()==(weight/'q.alpha.f32').read_bytes()
        for mode in ['cpu-low','diag-off','diag-on','cpu-float','gpu-high']:
            p=d/f'{kind}-{mode}';result=load(p/'result.json');assert result['valid'] and result['exit_code']==0
            source=load(p/'input-source.json');assert sha(R.parent/source['file'])==source['sha256']
            meta=load(p/'out/sample.meta.json')
            ys=[read(p/f'out/sample.r{i}.f32','<f4').reshape(n,2048) for i in range(3)]
            assert all(np.isfinite(y).all() for y in ys) and np.array_equal(ys[0],ys[1]) and np.array_equal(ys[1],ys[2])
            assert (p/'out/sample.r0.f32').read_bytes()==(p/'out/sample.r1.f32').read_bytes()==(p/'out/sample.r2.f32').read_bytes()
            for i in [1,2]:assert np.array_equal(read(p/f'out/sample.r{i}.conv_input.f32','<f4').reshape(n,1024),x)
            for row in meta['runs']:
                assert row['exit_code']==row['wait']==0 and sum(op['type']=='Convolution' for op in row['ops'])==1
                assert all(op['type'] in ['Convolution','Raster'] for op in row['ops'])
            timings.append({'kind':kind,'mode':mode,'wall_ms':[row['diagnostic_wall_ns']/1e6 for row in meta['runs']],'scope':'host runSessionWithCallBackInfo including callback file copies and, if enabled, runtime tracing; not kernel performance'})
        # Actual executor entry (after all wrapping), every first and subsequent execution.
        for i in range(3):
            t=base/f'trace.r{i}.exec';m=tsv(Path(str(t)+'.meta.tsv'))
            assert all(m[k]==str(v) for k,v in {'bytes':2,'pack':8,'ic':1024,'oc':2048,'dynamicOption':0,'blockNum':16,'inputBlockNum':1,'im2colBasedInt8':1,'useBatchQuan':1,'splitByOc':1,'weightQuantInfoMode':0,'weightBits':4,'UNIT':8,'SRC_UNIT':8,'DST_XUNIT':10,'q0_EP':n,'q0_LU':128,'q0_LP':8,'q0_threads':1,'q0_tId':0,'q0_zero':0,'quant_calls':1,'FPCR':0}.items())
            def unpack(name,dtype):return read(Path(str(t)+'.'+name+'.bin'),dtype).reshape(128,n,8).transpose(1,0,2).reshape(n,1024)
            actualx=unpack('entry_packed','<f2').astype('f4');pre=unpack('q0_pre','<f2').astype('f4');qx=unpack('q0_integer','i1')
            assert actualx.tobytes()==x.tobytes() and pre.tobytes()==x.tobytes()
            qref=read(ref/'reference.q.i8','i1').reshape(n,1024);qs=read(ref/'reference.qscale.f32','<f4');ds=read(ref/'reference.dscale.f32','<f4')
            assert np.array_equal(qx,qref)
            assert np.array_equal(qs,read(Path(str(t)+'.q0_qscale.bin'),'<f4')) and np.array_equal(ds,read(Path(str(t)+'.q0_dscale.bin'),'<f4'))
            assert np.array_equal(read(Path(str(t)+'.q0_absmax.bin'),'<f2').astype('f4'),np.abs(x).max(axis=1))
            yp=read(Path(str(t)+'.output_packed.bin'),'<f2').reshape(256,n,8).transpose(1,0,2).reshape(n,2048).astype('f4')
            cpu=read(d/f'{kind}-cpu-low/out/sample.r{i}.f32','<f4').reshape(n,2048);assert np.array_equal(yp,cpu)
            assert read(Path(str(t)+'.bias.bin'),'<f4').size==2048 and not np.any(read(Path(str(t)+'.bias.bin'),'<f4'))
            assert np.array_equal(read(Path(str(t)+'.relu.bin'),'<f2').astype('f4'),[-65504,65504])
            packedW=read(Path(str(t)+'.weight_packed.bin'),'u1').reshape(256,16,320)
            sc=packedW[:,:,256:288].copy().view('<f4').reshape(256,16,8).transpose(0,2,1).reshape(2048,16)
            off=packedW[:,:,288:320].copy().view('<f4').reshape(256,16,8).transpose(0,2,1).reshape(2048,16)
            assert np.array_equal(sc,alpha[:,:,1]) and np.array_equal(off,alpha[:,:,0]-np.float32(8)*alpha[:,:,1])
            # Independent integer dot and input sums, useful for inspecting the exact contract.
            if i==1:
                dots=np.empty((n,16,2048),dtype='<i4');sums=np.empty((n,16),dtype='<i4')
                for bl in range(16):
                    xi=qx[:,bl*64:(bl+1)*64].astype('i4');wu=wi[:,bl*64:(bl+1)*64].astype('i4')+8
                    dots[:,bl,:]=xi@wu.T;sums[:,bl]=xi.sum(axis=1)
                dots.tofile(ref/'independent-dots.i32');sums.tofile(ref/'independent-input-sums.i32')
                for name in ['MNNAbsMax','MNNQuantScale','MNNDynamicQuant','mGemmKernel','SumByAxis']:
                    offset=int(m[name+'_offset']);matches=[]
                    for line in linkmap.splitlines():
                        fields=line.split(None,4)
                        if len(fields)==5:
                            try:addr=int(fields[0],16)
                            except ValueError:continue
                            if addr==offset and not fields[4].startswith(('$','CMakeFiles','/')):matches.append(fields[4])
                    assert matches,(name,hex(offset));functions.append({'kind':kind,'field':name,'elf_offset_hex':hex(offset),'map_symbols':matches})
        B=read(ref/'reference.B.f32','<f4').reshape(n,2048);A=read(ref/'reference.A.f64','<f8').reshape(n,2048)
        Bi=read(ref/'reference.B-ideal.f64','<f8').reshape(n,2048);Bp=read(ref/'reference.B-prehalf.f32','<f4').reshape(n,2048)
        values={'A64':A,'B64_ideal':Bi,'B32_prehalf':Bp,'B16_contract':B}
        for mode in ['cpu-low','diag-off','diag-on','cpu-float','gpu-high']:values[mode]=read(d/f'{kind}-{mode}/out/sample.r1.f32','<f4').reshape(n,2048)
        assert np.array_equal(values['cpu-low'],values['diag-on']) and np.array_equal(values['cpu-low'],values['diag-off']) and np.array_equal(B,values['cpu-low'])
        assert (ref/'reference.B.f32').read_bytes()==(d/f'{kind}-cpu-low/out/sample.r1.f32').read_bytes()==(d/f'{kind}-diag-off/out/sample.r1.f32').read_bytes()==(d/f'{kind}-diag-on/out/sample.r1.f32').read_bytes()
        for a,b in [('A64','cpu-float'),('A64','gpu-high'),('B16_contract','cpu-low'),('A64','B16_contract'),('A64','B64_ideal'),('B64_ideal','B32_prehalf'),('B32_prehalf','B16_contract')]:metrics.append({'kind':kind,'reference':a,'compared':b,**metric(values[a],values[b])})
        checks.append({'kind':kind,'tokens':n,'independent_input_case':True,'all_three_executor_entries_match':True,'all_three_quantized_inputs_match':True,'all_three_scales_match':True,'runtime_decoded_weights_and_alpha_match':True,'prepared_scale_offset_match':True,'tracing_on_off_and_archive_output_identical':True,'independent_contract_matches_cpu_all_elements':True,'q_min':int(qref.min()),'q_max':int(qref.max()),'qscale_range':[float(qs.min()),float(qs.max())],'dscale_range':[float(ds.min()),float(ds.max())],'integer_dot_range':[int(dots.min()),int(dots.max())]})
    first=[]
    for kind,n in [('synthetic',8),('natural',13)]:
        old=read(R/f'evidence/reference-attempt1/{kind}/reference.B.f32','<f4');cpu=read(d/f'{kind}-cpu-low/out/sample.r1.f32','<f4');ix=np.nonzero(old!=cpu)[0]
        first.append({'kind':kind,'mismatch_count':int(ix.size),'details':[{'token':int(i//2048),'channel':int(i%2048),'initial_reference':float(old[i]),'cpu':float(cpu[i])} for i in ix]})
    result={'primary_session':str(d.relative_to(R)),'decision':'A','independent_input_cases':2,'functional_checks':checks,'metrics':metrics,'actual_function_pointers':functions,'diagnostic_timings':timings,'initial_reference_attempt':first,'new_runtime_experiments_required':False}
    (R/'analysis/results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (R/'analysis/errors.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    print('Decision A: independent quantized contract exactly reproduces both cases')
    for x in metrics:print(x['kind'],x['reference'],x['compared'],x['relative_rmse'],x['max_abs'])
if __name__=='__main__':main()
