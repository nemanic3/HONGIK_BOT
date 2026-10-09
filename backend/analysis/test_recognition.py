from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from .engine import evaluate_rules
from .test_engine import course, policy

class RecognitionTests(SimpleTestCase):
    def spec(self):
        return policy([{'id':'total','kind':'credits','minimum':6,'roles':['total']}],[{'code':'A','name':'New'},{'code':'B','name':'Old'}])
    def result(self,rows,spec=None):
        return evaluate_rules(spec or self.spec(),{'courses':rows})
    def test_retake_without_policy_does_not_choose_best_or_latest(self):
        r=self.result([course('A',grade='A0',semester='2030-1'),course('A',grade='C+',semester='2031-1')])
        self.assertEqual(r['criteria'][0]['completed'],0)
        self.assertEqual(r['status'],'needs_verification')
    def test_user_selection_counts_once_and_preserves_history(self):
        r=self.result([course('A',credit_decision='exclude',grade='',credit=None),course('A',semester='2031-1',credit_decision='include',retake=True)])
        self.assertEqual(r['criteria'][0]['completed'],3)
        self.assertEqual(len(r['courses']),2)
        self.assertFalse(r['courses'][0]['credit_counted'])
        self.assertEqual(r['status'],'needs_verification')
    def test_two_includes_cannot_double_count(self):
        r=self.result([course('A',credit_decision='include'),course('A',credit_decision='include',semester='2031-1')])
        self.assertEqual(r['criteria'][0]['completed'],0)
    def test_fail_does_not_cancel_later_pass(self):
        r=self.result([course('A',grade='F'),course('A',grade='P',semester='2031-1')])
        self.assertEqual(r['criteria'][0]['completed'],3)
    def test_same_course_renamed_code_shares_identity_but_replacement_does_not(self):
        for kind,expected in [('same_course',0),('replacement',6)]:
            spec=self.spec();spec['data']['course_relations']=[{'kind':kind,'official_verified':True,'from_code':'B','to_code':'A','source_document':'Synthetic policy fixture','source':{'pdf_page':4,'printed_page':'2'}}]
            r=self.result([course('A'),course('B')],spec)
            self.assertEqual(r['criteria'][0]['completed'],expected)
    def test_relation_without_source_rejected(self):
        spec=self.spec();spec['data']['course_relations']=[{'kind':'same_course','from_code':'B','to_code':'A'}]
        with self.assertRaises(ValidationError): self.result([course('A')],spec)
    def test_client_cannot_invent_same_course_relation(self):
        r=self.result([course('A'),course('B',same_course='A',aliases=['A'])])
        self.assertEqual(r['criteria'][0]['completed'],6)

    def test_missing_ocr_rows_block_verified_completion(self):
        r=evaluate_rules(self.spec(),{'courses':[course('A',6)],'incomplete':True})
        self.assertEqual(r['criteria'][0]['status'],'needs_verification')

    def test_same_name_changed_code_needs_evidence_and_replacement_stays_distinct(self):
        spec=self.spec()
        rows=[course('A',name='같은과목'),course('B',name='같은과목',semester='2031-1')]
        result=self.result(rows,spec)
        self.assertEqual(result['criteria'][0]['completed'],0)
        self.assertTrue(all(r['identity_conflict'] for r in result['courses']))
        spec['data']['course_relations']=[{'kind':'replacement','official_verified':True,'from_code':'B','to_code':'A','source_document':'Synthetic fixture','source':{'pdf_page':3,'printed_page':'1'}}]
        self.assertEqual(self.result(rows,spec)['criteria'][0]['completed'],6)
