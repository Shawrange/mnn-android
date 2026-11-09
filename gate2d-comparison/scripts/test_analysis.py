import unittest
from analyze import stats,aggregate
from run import parse
class Contracts(unittest.TestCase):
    def test_statistics(self):
        s=stats([1,2,3,4,5,6]);self.assertEqual(s['median'],3.5);self.assertEqual(s['n'],6);self.assertAlmostEqual(s['sample_sd'],1.8708286933869707)
    def test_native_contract(self):
        d={'backend':'OPENCL','threads':4,'precision':2,'memory':2,'power':0,'quantKv':0,'flashAttention':1,'useMmap':False,'results':[{'type':'prefill_and_decode','prompt_len':32,'generate_len':64,'prefill_tps':320,'decode_tps':64}]}
        v=parse(d,'opencl',32,64);self.assertEqual(v['prefill_ms_derived'],100);self.assertEqual(v['decode_ms_derived'],1000);self.assertEqual(v['opencl_mode_bits'],580);self.assertIsNone(v['cpu_threads'])
        d['results'][0]['generate_len']=16
        with self.assertRaises(ValueError):parse(d,'opencl',32,64)
    def test_paired_direction_and_failure_exclusion(self):
        def s(b,block,ppms,decms):return dict(backend=b,block=block,pp=32,tg=64,index=block,status='success',prefill_tps=32000/ppms,decode_tps=64000/decms,prefill_ms_derived=ppms,decode_ms_derived=decms,max_rss_kib=100,process_wall_seconds_device=2)
        result=aggregate([s('cpu',1,200,500),s('opencl',1,100,1000),dict(s('cpu',2,1,1),status='failed')])
        self.assertEqual(result['successful'],2);self.assertEqual(len(result['failed']),1);self.assertEqual(len(result['pairs']),1);p=result['pairs'][0];self.assertEqual(p['prefill_cpu_over_gpu'],2);self.assertEqual(p['decode_cpu_over_gpu'],.5);self.assertAlmostEqual(p['timer_sum_cpu_over_gpu'],700/1100)
if __name__=='__main__':unittest.main()
