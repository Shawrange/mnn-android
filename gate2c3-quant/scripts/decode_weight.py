from pathlib import Path
import numpy as np,json,struct
R=Path(__file__).resolve().parents[1];d=R/'evidence/weight';m=json.loads((d/'q.meta.json').read_text())
raw=(d/'q.raw_weight.bin').read_bytes();dim=raw[0];shape=struct.unpack_from('<' + ('I' if m['shapeInt32'] else 'H')*dim,raw,1)
pos=1+dim*(4 if m['shapeInt32'] else 2);count=raw[pos] or 256;pos+=1
samples=np.frombuffer(raw[pos:pos+count],dtype='i1').copy();samples.sort();pos+=count
assert dim==2 and shape==(2048,1024) and count==16 and np.array_equal(samples,np.arange(-8,8,dtype='i1'))
packed=np.frombuffer(raw[pos:],dtype='u1');assert packed.size==2048*1024//2
q=np.empty(packed.size*2,dtype='i1');q[0::2]=samples[packed>>4];q[1::2]=samples[packed&15]
alpha=np.fromfile(d/'q.raw_alpha.bin',dtype='<f4').reshape(2048,16,2)
assert m['aMin']==1 and m['quantScale']==1 and m['scaleStorage']==0 and not m['has_scaleInt']
assert m['external'][3]==0 and m['inline_bias_elements']==0
q.tofile(d/'q.decoded.i8');alpha.tofile(d/'q.alpha.f32');np.zeros(2048,dtype='<f4').tofile(d/'q.bias.f32')
(d/'independent-decode.json').write_text(json.dumps({'shape':shape,'header_bytes':pos,'sample_count':count,'samples':samples.tolist(),'alpha_shape':list(alpha.shape),'weight_block_channels':64,'bias':'implicit positive zero','aMin':m['aMin'],'loader_fold_applied':False,'weight_formula':'signed int4 * raw scale + raw offset','independent_decoder':'Python struct/NumPy only; no MNN loader linked'},indent=2))
print('Decoded original first-Q weights independently')
