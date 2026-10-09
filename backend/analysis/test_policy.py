from copy import deepcopy
from django.test import SimpleTestCase
from .policy import bundle, select_policy


class PolicySelectionTests(SimpleTestCase):
    def test_cohort_and_track_are_independent(self):
        a=select_policy('컴퓨터공학과',2025,'accredited')
        b=select_policy('컴퓨터공학과',2025,'non_accredited')
        a_rules={r['id']:r for r in a['data']['criteria']}
        b_rules={r['id']:r for r in b['data']['criteria']}
        self.assertEqual(a_rules['major']['minimum'],54)
        self.assertEqual(a_rules['msc']['minimum'],30)
        self.assertEqual(b_rules['major']['minimum'],50)
        self.assertEqual(b_rules['msc']['minimum'],23)
        self.assertEqual(b_rules['msc_math_science']['minimum'],17)
        self.assertEqual(b_rules['msc']['source']['pdf_page'],10)

    def test_designated_computing_credit_minimum_is_separate_from_course_presence(self):
        p=select_policy('컴퓨터공학과',2025,'non_accredited')
        assert p is not None
        rules={r['id']:r for r in p['data']['criteria']}
        self.assertEqual(rules.get('msc_computing',{}).get('minimum'),6)
        numerical=next(row for row in p['data']['catalog'] if row['code']=='012308')
        self.assertIsNone(numerical.get('sw_level'))

    def test_transition_years_and_unknown_profile_do_not_fallback(self):
        for year,expected in [(2019,18),(2020,24),(2023,24),(2024,23)]:
            with self.subTest(year=year):
                p=select_policy('컴퓨터공학과',year,'non_accredited')
                self.assertEqual(next(r['minimum'] for r in p['data']['criteria'] if r['id']=='msc'),expected)
        self.assertIsNone(select_policy('다른학과',2025,'non_accredited'))
        self.assertIsNone(select_policy('컴퓨터공학과',2025,''))
        self.assertIsNone(select_policy('컴퓨터공학과',2027,'non_accredited'))

    def test_legacy_years_are_covered_without_inventing_missing_values(self):
        old=select_policy('컴퓨터공학과',2003,'non_accredited')
        self.assertIsNotNone(old)
        self.assertTrue(any(r['kind']=='review' for r in old['data']['criteria']))
        self.assertFalse(old['source_verified'])
        again=deepcopy(select_policy('컴퓨터공학과',2025,'non_accredited'))
        again['data']['criteria'].clear()
        self.assertTrue(select_policy('컴퓨터공학과',2025,'non_accredited')['data']['criteria'])

    def test_engineering_sources_keep_exact_pdf_and_printed_page_pairs(self):
        expected = {89: '공-1', 98: '공-10', 99: '공-11'}
        found = set()
        for spec in bundle()['policies']:
            for row in spec['data']['criteria'] + spec['data']['catalog']:
                for source in [row['source'], *row.get('additional_sources', [])]:
                    if source['pdf_page'] in expected:
                        found.add(source['pdf_page'])
                        self.assertEqual(source['printed_page'], expected[source['pdf_page']])
        self.assertEqual(found, set(expected))

    def test_credit_obligations_have_documented_dual_references_and_new_version(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        rules = {r['id']: r for r in spec['data']['criteria']}
        self.assertEqual(rules['msc_designated']['source'], {'pdf_page': 10, 'printed_page': '8'})
        self.assertEqual(rules['basic_general']['source'], {'pdf_page': 10, 'printed_page': '8'})
        for name in ['writing', 'university_english', 'english', 'special_general']:
            self.assertEqual(rules[name]['source'], {'pdf_page': 34, 'printed_page': '32'})
        self.assertEqual(spec['version'], 'hongik-cs-2026-provided-draft-v2')
        self.assertFalse(spec['source_verified'])
