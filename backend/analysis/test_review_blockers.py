"""Regressions for the final backend review (all DB writes are test-only)."""
from copy import deepcopy
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase
from common.course_schema import CourseSchemaError

from .engine import evaluate_rules
from .models import RequirementRuleSet
from .policy import select_policy
from .test_engine import course
from .test_engine import policy as fixture_policy


class CreditedObligationTests(SimpleTestCase):
    def evaluate(self, courses, year=2025, track='non_accredited'):
        spec = select_policy('컴퓨터공학과', year, track)
        return {row['id']: row for row in evaluate_rules(spec, {'courses': courses})['criteria']}

    def test_other_computing_credits_cannot_replace_designated_pair_credits(self):
        for track in ('accredited', 'non_accredited'):
            for year in (2022, 2025, 2026):
                with self.subTest(track=track, year=year):
                    result = self.evaluate([course('012305', 0), course('101810', 0), course('012301'), course('012313')], year, track)
                    self.assertEqual(result['msc_computing']['status'], 'met')
                    self.assertEqual(result['msc_designated']['status'], 'not_met')
                    self.assertEqual(result['msc_designated']['required_credit'], 6)
                    self.assertEqual(result['msc_designated']['completed_credit'], 0)

    def test_individual_required_groups_need_their_own_credits(self):
        for rule_id, code, minimum in [('writing', '001012', 3), ('university_english', '001023', 3), ('english', '007114', 2), ('special_general', '008751', 3)]:
            with self.subTest(rule=rule_id):
                for credit in (0, minimum - 0.5):
                    result = self.evaluate([course(code, credit)])
                    self.assertEqual(result[rule_id]['status'], 'not_met')
                    self.assertEqual(result[rule_id]['required_credit'], minimum)
                self.assertEqual(self.evaluate([course(code, minimum)])[rule_id]['status'], 'met')

    def test_basic_general_minimum_cannot_be_replaced_by_other_general_credits(self):
        result = self.evaluate([course('001012', 2), course('001023', 3), course('002590', 30)])
        self.assertEqual(result['general']['status'], 'met')
        self.assertEqual(result.get('basic_general', {}).get('status'), 'not_met')
        self.assertEqual(result['basic_general']['required'], 6)
        self.assertEqual(result['basic_general']['completed'], 5)

    def test_designated_pair_requires_both_credited_courses_and_six_credits(self):
        self.assertEqual(self.evaluate([course('012305', 6)])['msc_designated']['status'], 'not_met')
        self.assertEqual(self.evaluate([course('012305', 6), course('101810', 0)])['msc_designated']['status'], 'not_met')
        self.assertEqual(self.evaluate([course('012305'), course('101810')])['msc_designated']['status'], 'met')


def malformed_policies():
    base = select_policy('컴퓨터공학과', 2025, 'non_accredited')
    mutations = [
        ('data_mapping', lambda p: p.update(data=[])),
        ('boolean_schema', lambda p: p['data'].update(schema_version=True)),
        ('missing_schema', lambda p: p['data'].pop('schema_version')),
        ('empty_rules', lambda p: p['data'].update(criteria=[])),
        ('rule_mapping', lambda p: p['data']['criteria'].__setitem__(0, [])),
        ('catalog_mapping', lambda p: p['data']['catalog'].__setitem__(0, [])),
        ('missing_minimum', lambda p: p['data']['criteria'][0].pop('minimum')),
        ('negative_minimum', lambda p: p['data']['criteria'][0].update(minimum=-1)),
        ('boolean_minimum', lambda p: p['data']['criteria'][0].update(minimum=True)),
        ('infinite_minimum', lambda p: p['data']['criteria'][0].update(minimum=float('inf'))),
        ('nan_minimum', lambda p: p['data']['criteria'][0].update(minimum=float('nan'))),
        ('negative_cap', lambda p: p['data']['criteria'][0].update(cap=-1)),
        ('missing_cap', lambda p: p['data']['criteria'][0].pop('cap')),
        ('roles_mapping', lambda p: p['data']['criteria'][0].update(roles={})),
        ('empty_roles', lambda p: p['data']['criteria'][0].update(roles=[])),
        ('source_mapping', lambda p: p['data']['criteria'][0].update(source=[])),
        ('boolean_page', lambda p: p['data']['criteria'][0]['source'].update(pdf_page=True)),
        ('zero_page', lambda p: p['data']['criteria'][0]['source'].update(pdf_page=0)),
        ('missing_printed_ref', lambda p: p['data']['criteria'][0]['source'].pop('printed_page')),
        ('blank_printed_ref', lambda p: p['data']['criteria'][0]['source'].update(printed_page='')),
        ('duplicate_rule_id', lambda p: p['data']['criteria'].append(deepcopy(p['data']['criteria'][0]))),
        ('duplicate_catalog_identity', lambda p: p['data']['catalog'].append(deepcopy(p['data']['catalog'][0]))),
        ('missing_catalog_name', lambda p: p['data']['catalog'][0].pop('name')),
        ('catalog_roles_mapping', lambda p: p['data']['catalog'][0].update(roles={})),
        ('catalog_alias_mapping', lambda p: p['data']['catalog'][0].update(aliases={})),
        ('catalog_source_mapping', lambda p: p['data']['catalog'][0].update(source=[])),
        ('invalid_sw_level', lambda p: p['data']['catalog'][0].update(sw_level=True)),
    ]
    for name, change in mutations:
        spec = deepcopy(base)
        change(spec)
        yield name, spec
    for name, fields in [
        ('empty_groups', {'groups': []}), ('empty_group', {'groups': [[]]}),
        ('group_mapping', {'groups': [{}]}), ('unknown_group_code', {'groups': [['missing']]}),
        ('duplicate_group_code', {'groups': [['001012', '001012']]}),
        ('duplicate_groups', {'groups': [['001012'], ['001012']]}),
        ('zero_count', {'minimum_count': 0}), ('boolean_count', {'minimum_count': True}),
        ('excess_count', {'minimum_count': 3}), ('negative_group_credit', {'minimum_credit': -1}),
        ('infinite_group_credit', {'minimum_credit': float('inf')}),
    ]:
        spec = deepcopy(base)
        next(r for r in spec['data']['criteria'] if r['id'] == 'writing').update(fields)
        yield name, spec


class StrictPolicyValidationTests(SimpleTestCase):
    def test_model_clean_rejects_malformed_rules_with_validation_error(self):
        for name, spec in malformed_policies():
            with self.subTest(case=name):
                with self.assertRaises(ValidationError):
                    RequirementRuleSet(**spec).clean()

    def test_evaluator_rejects_malformed_rules_before_interpretation(self):
        for name, spec in malformed_policies():
            with self.subTest(case=name):
                with self.assertRaises(ValidationError):
                    evaluate_rules(spec, {'courses': []})

    def test_import_rejects_malformed_policy_as_controlled_command_error(self):
        for name, spec in malformed_policies():
            with self.subTest(case=name):
                with patch('analysis.management.commands.load_curriculum_rules.bundle', return_value={'policies': [spec]}):
                    with self.assertRaises(CommandError):
                        call_command('load_curriculum_rules', stdout=StringIO())

    def test_unknown_kind_is_review_only_even_with_verified_source(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        spec['source_verified'] = True
        spec['data']['criteria'] = [dict(spec['data']['criteria'][0], kind='future-kind')]
        RequirementRuleSet(**spec).clean()
        result = evaluate_rules(spec, {'courses': []})
        self.assertEqual(result['status'], 'needs_verification')
        self.assertEqual(result['criteria'][0]['status'], 'needs_verification')


class MalformedPolicySaveTests(TestCase):
    def test_save_rejects_invalid_rules_without_persisting(self):
        for name, spec in malformed_policies():
            with self.subTest(case=name):
                with self.assertRaises(ValidationError):
                    RequirementRuleSet(**spec).save()
        self.assertEqual(RequirementRuleSet.objects.count(), 0)


class AggregateCreditTests(SimpleTestCase):
    def test_finite_individual_credits_cannot_overflow_aggregate_json(self):
        spec = fixture_policy([{'id': 'total', 'kind': 'credits', 'roles': ['total'], 'minimum': 3}], [])
        with self.assertRaises(CourseSchemaError):
            evaluate_rules(spec, {'courses': [course('A', 1e308), course('B', 1e308)]})


class ImmutableRuleVersionTests(TestCase):
    def test_existing_version_cannot_change_contents_source_or_scope(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        original = RequirementRuleSet.objects.create(**spec)
        changes = {
            'data': dict(spec['data'], criteria=[dict(spec['data']['criteria'][0], minimum=1)]),
            'source_document': 'different.pdf', 'source_sha256': '0' * 64,
            'source_verified': True, 'admission_year_from': 2023,
            'admission_year_to': 2027, 'curriculum_year': 2027,
            'accreditation_track': 'accredited', 'major': 'different',
            'campus': 'different', 'version': 'renamed-in-place',
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                row = RequirementRuleSet.objects.get(pk=original.pk)
                setattr(row, field, value)
                with self.assertRaises(ValidationError):
                    row.save(update_fields=[field])
                original.refresh_from_db()
                self.assertEqual(getattr(original, field), spec[field])

    def test_reconstructed_instance_cannot_overwrite_existing_version(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        row = RequirementRuleSet.objects.create(**spec)
        modified = dict(spec, source_verified=True)
        with self.assertRaises(ValidationError):
            RequirementRuleSet(pk=row.pk, **modified).clean()

    def test_unchanged_save_and_new_row_with_new_version_remain_allowed(self):
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        row = RequirementRuleSet.objects.create(**spec)
        row.save()
        spec['version'] += '-verified'
        spec['source_verified'] = True
        new = RequirementRuleSet.objects.create(**spec)
        self.assertNotEqual(row.pk, new.pk)
        row.refresh_from_db()
        self.assertFalse(row.source_verified)
        self.assertEqual(RequirementRuleSet.objects.count(), 2)
