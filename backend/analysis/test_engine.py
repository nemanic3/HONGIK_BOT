from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from copy import deepcopy
from .engine import evaluate_rules
from .policy import select_policy


def zero_credit_area_courses():
    return [course(code) for code in ('002590', '002529', '002207', '002056', '002558', '002046', '001012', '001023')] + [course('002605', 0)]


def zero_credit_sw_courses():
    return [course('012305', 0), course('002534'), course('002618'), course('961823')]


def course(code, credit=3, grade='A+', **extra):
    return {'code':code,'name':code,'credit':credit,'grade':grade,'semester':'1-1','type':'과목', **extra}


def policy(criteria, catalog):
    # Valid declarative fixtures; schema and dual provenance are mandatory.
    criteria, catalog = deepcopy(criteria), deepcopy(catalog)
    for row in [*criteria, *catalog]:
        row.setdefault('source', {'pdf_page': 1, 'printed_page': 'fixture-1'})
    return {'source_verified':True, 'data':{'schema_version':1,'criteria':criteria,'catalog':catalog}}


class EngineTests(SimpleTestCase):
    def test_real_policy_zero_credit_language_does_not_cover_mandatory_area(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        courses = zero_credit_area_courses()
        result = evaluate_rules(spec, {'courses': courses})
        rules = {row['id']: row for row in result['criteria']}
        self.assertEqual(rules['areas']['status'], 'not_met')
        self.assertEqual(rules['areas']['completed'], 6)
        self.assertEqual(rules['areas']['required'], 6)
        self.assertNotIn('제2외국어와 한문', rules['areas']['covered'])
        self.assertEqual(rules['areas']['missing'], ['제2외국어와 한문'])
        self.assertEqual(rules['total']['completed'], 24)
        self.assertEqual(len(result['courses']), len(courses))
        self.assertEqual(result['by_semester']['1-1'][-1]['credit'], 0)
        self.assertEqual(result['status'], 'needs_verification')
        self.assertTrue(any('공식 최종본' in warning for warning in result['warnings']))
        courses[-1]['credit'] = 3
        positive = evaluate_rules(spec, {'courses': courses})
        self.assertEqual(next(row for row in positive['criteria'] if row['id'] == 'areas')['status'], 'met')

    def test_real_policy_zero_credit_advanced_course_does_not_fill_sw_slot(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        courses = zero_credit_sw_courses()
        result = evaluate_rules(spec, {'courses': courses})
        rules = {row['id']: row for row in result['criteria']}
        self.assertEqual(rules['sw']['status'], 'not_met')
        self.assertEqual(rules['sw']['completed'], 9)
        self.assertEqual(rules['sw']['required'], 9)
        self.assertEqual(rules['sw']['slots_filled'], 2)
        self.assertTrue(rules['sw']['missing'])
        self.assertEqual(rules['total']['completed'], 9)
        self.assertEqual(len(result['courses']), len(courses))
        self.assertEqual(result['by_semester']['1-1'][0]['credit'], 0)
        self.assertEqual(result['status'], 'needs_verification')
        self.assertTrue(any('공식 최종본' in warning for warning in result['warnings']))
        courses[0]['credit'] = 3
        positive = evaluate_rules(spec, {'courses': courses})
        sw = next(row for row in positive['criteria'] if row['id'] == 'sw')
        self.assertEqual(sw['status'], 'met')
        self.assertEqual(sw['slots_filled'], 3)
        self.assertEqual(sw['completed'], 12)

    def test_only_exact_boolean_true_marks_outer_policy_source_verified(self):
        spec = policy([{'id': 'total', 'kind': 'credits', 'minimum': 3, 'roles': ['total']}], [{'code': 'A', 'name': 'A'}])
        document = {'courses': [course('A')]}
        for flag in ('false', 'true', 1, False, None):
            with self.subTest(flag=flag):
                spec['source_verified'] = flag
                result = evaluate_rules(spec, document)
                self.assertEqual(result['criteria'][0]['status'], 'met')
                self.assertEqual(result['status'], 'needs_verification')
                self.assertTrue(any('공식 최종본' in warning for warning in result['warnings']))
        spec.pop('source_verified')
        self.assertEqual(evaluate_rules(spec, document)['status'], 'needs_verification')
        spec['source_verified'] = True
        result = evaluate_rules(spec, document)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['warnings'], [])

    def test_real_policy_additional_sources_survive_evaluation_without_aliasing(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        result = evaluate_rules(spec, {'courses': []})
        rule = next(row for row in spec['data']['criteria'] if row['id'] == 'msc_designated')
        item = next(row for row in result['criteria'] if row['id'] == 'msc_designated')
        self.assertEqual(item.get('additional_sources'), rule['additional_sources'])
        self.assertEqual(item['source'], rule['source'])
        item['additional_sources'][0]['pdf_page'] = 1
        self.assertEqual(rule['additional_sources'][0]['pdf_page'], 98)

    def test_credit_fraction_failing_grade_and_distinct_total(self):
        spec = policy([{'id':'total','kind':'credits','minimum':6,'roles':['total']}], [])
        result = evaluate_rules(spec, {'courses':[course('A',2.5),course('B',3),course('C',9,'F')]})
        item = result['criteria'][0]
        self.assertEqual(item['completed'],5.5)
        self.assertEqual(item['remaining'],0.5)
        self.assertEqual(item['status'],'not_met')

    def test_area_rule_requires_named_mandatory_areas_not_just_count(self):
        rule={'id':'areas','kind':'areas','minimum_count':2,'mandatory':['예술','언어']}
        catalog=[{'code':'A','name':'A','area':'예술'},{'code':'B','name':'B','area':'사회'}]
        item = evaluate_rules(policy([rule],catalog),{'courses':[course('A'),course('B')]})['criteria'][0]
        self.assertEqual(item['status'],'not_met')
        self.assertIn('언어',item['missing'])

    def test_advanced_sw_modules_substitute_lower_slots_but_basic_does_not(self):
        rule={'id':'sw','kind':'sw_modules','minimum':9}
        catalog=[{'code':x,'name':x,'sw_level':level} for x,level in [('A',3),('B',3),('C',3),('D',2),('E',2),('F',2)]]
        good=evaluate_rules(policy([rule],catalog),{'courses':[course('A'),course('B'),course('C')]})
        self.assertEqual(good['criteria'][0]['status'],'met')
        bad=evaluate_rules(policy([rule],catalog),{'courses':[course('D'),course('E'),course('F')]})
        self.assertEqual(bad['criteria'][0]['status'],'not_met')

    def test_duplicate_attempts_are_not_double_counted_or_silently_discarded(self):
        result=evaluate_rules(policy([{'id':'total','kind':'credits','minimum':3,'roles':['total']}],[]),{'courses':[course('A'),course('A',4,semester='2-1')]})
        self.assertEqual(result['criteria'][0]['status'],'needs_verification')
        self.assertEqual(result['status'],'needs_verification')
        self.assertEqual(len(result['courses']),2)

    def test_empty_rule_list_cannot_claim_completion(self):
        with self.assertRaises(ValidationError):
            evaluate_rules(policy([],[]),{'courses':[]})

    def test_repeated_same_alias_is_one_identity_not_ambiguous(self):
        rule={'id':'course','kind':'course_groups','groups':[['001009']]}
        row={'code':'001009','name':'영어','aliases':['영어']}
        result=evaluate_rules(policy([rule],[row]),{'courses':[dict(course('',3),name='영어')]})
        self.assertEqual(result['criteria'][0]['status'],'met')

    def test_unmatched_course_makes_absence_uncertain(self):
        rule={'id':'course','kind':'course_groups','groups':[['001009']]}
        result=evaluate_rules(policy([rule],[{'code':'001009','name':'영어'}]),{'courses':[dict(course('999999'),name='영어')]})
        self.assertEqual(result['criteria'][0]['status'],'needs_verification')

    def test_unverified_source_or_unknown_rule_cannot_become_complete(self):
        spec=policy([{'id':'unknown','kind':'new-rule'}],[])
        spec['source_verified']=False
        result=evaluate_rules(spec,{'courses':[]})
        self.assertEqual(result['status'],'needs_verification')
        self.assertEqual(result['criteria'][0]['status'],'needs_verification')
