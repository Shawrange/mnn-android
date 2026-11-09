import unittest
from score import grade
class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.case={'id':'x','category':'extraction','rule':'json_exact','gold':{'name':'小明','count':2},'variants':['{"name":"小明","count":2}']}
    def runtext(self,text,**kw):return dict(raw_text=text,status=1,stopped=True,runtime_ok=True,process_exit=0,**kw)
    def test_order_whitespace(self):self.assertTrue(grade(self.case,self.runtext(' { "count": 2, "name": "小明" }\n'))['success'])
    def test_type_is_strict(self):self.assertIn('schema_error',grade(self.case,self.runtext('{"name":"小明","count":"2"}'))['flags'])
    def test_bool_not_int(self):self.assertFalse(grade(self.case,self.runtext('{"name":"小明","count":true}'))['success'])
    def test_extra_key(self):self.assertFalse(grade(self.case,self.runtext('{"name":"小明","count":2,"x":0}'))['success'])
    def test_duplicate_key(self):self.assertIn('parse_failure',grade(self.case,self.runtext('{"name":"错","name":"小明","count":2}'))['flags'])
    def test_code_fence(self):self.assertIn('parse_failure',grade(self.case,self.runtext('```json\n{"name":"小明","count":2}\n```'))['flags'])
    def test_truncation_not_pass(self):
        r=self.runtext('{"name":"小明","count":2}');r.update(status=2,stopped=False);g=grade(self.case,r);self.assertFalse(g['success']);self.assertIn('truncated',g['flags'])
    def test_failed_process_not_pass(self):
        r=self.runtext('{"name":"小明","count":2}');r['process_exit']=1;self.assertFalse(grade(self.case,r)['success'])
    def test_no_explanation_stripping(self):
        c={'id':'c','category':'classification','rule':'exact','gold':'咨询','variants':['咨询']};self.assertFalse(grade(c,self.runtext('答案：咨询'))['success'])
    def test_explicit_variants(self):
        c={'id':'q','category':'qa','rule':'exact','gold':'北京','variants':['北京','北京市']};self.assertTrue(grade(c,self.runtext('北京市'))['success'])
if __name__=='__main__':unittest.main()
