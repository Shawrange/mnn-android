"""Small parser checks using real Gate 0 JSON and failure conditions."""
from pathlib import Path
import copy,sys,unittest
sys.path.insert(0,str(Path(__file__).parent))
from run_bench import load,parse_benchmark,parse_state

class ParserTests(unittest.TestCase):
    def setUp(self):
        self.raw=load(Path(__file__).resolve().parents[1]/'evidence/fixtures/gate0-real-bench.json')
    def test_real_gate0_json(self):
        result=parse_benchmark(self.raw,128,64,{})
        self.assertAlmostEqual(result['prefill_tps'],229.7126079918452)
        self.assertIsNone(result['ttft_ms'])
        self.assertEqual(result['effective_dynamic_option'],0)
    def test_wrong_backend_is_rejected(self):
        self.raw['backend']='OPENCL'
        with self.assertRaises(ValueError):parse_benchmark(self.raw,128,64,{})
    def test_wrong_workload_is_rejected(self):
        with self.assertRaises(ValueError):parse_benchmark(self.raw,512,64,{})
    def test_missing_nonfinite_and_zero_are_rejected(self):
        for value in [None,0,float('nan'),float('inf')]:
            self.raw['results'][0]['decode_tps']=value
            with self.assertRaises(ValueError):parse_benchmark(self.raw,128,64,{})
    def test_extra_results_are_rejected(self):
        self.raw['results'].append(copy.deepcopy(self.raw['results'][0]))
        with self.assertRaises(ValueError):parse_benchmark(self.raw,128,64,{})
    def test_only_current_hal_temperature_is_used(self):
        raw='Cached temperatures:\nTemperature{mValue=99.0, mType=3, mName=skin, mStatus=0}\nCurrent temperatures from HAL:\nTemperature{mValue=34.0, mType=3, mName=skin, mStatus=0}\nCurrent cooling devices from HAL:\n'
        self.assertEqual(parse_state(raw)['skin_c'],34.0)
    def test_adb_crlf_frequency_fields(self):
        raw='@@POLICY policy0\r\nscaling_cur_freq=2400000\r\nscaling_max_freq=2745600\r\n@@MEMORY\r\n'
        self.assertEqual(parse_state(raw)['policies']['policy0']['scaling_cur_freq'],'2400000')

if __name__=='__main__':unittest.main()
