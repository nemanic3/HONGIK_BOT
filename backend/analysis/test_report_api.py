from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User
from transcripts.models import Transcript
from .models import RequirementRuleSet
from .policy import select_policy


class ReportAPITests(TestCase):
    def setUp(self):
        self.user=User.objects.create(username='T700001',student_id='T700001',full_name='테스트',major='컴퓨터공학과',admission_year=2025,accreditation_track='non_accredited')
        self.other=User.objects.create(username='T700002',student_id='T700002',full_name='테스트')
        self.client=APIClient()
        self.client.force_authenticate(self.user)
        self.transcript=Transcript.objects.create(user=self.user)

    def test_real_policy_zero_credit_language_does_not_cover_mandatory_area(self):
        from .test_engine import zero_credit_area_courses
        courses = zero_credit_area_courses()
        self.transcript.confirm_courses({'courses': courses}, confirmed_by=self.user)
        response = self.client.get('/api/analysis/report/', {'transcript_id': self.transcript.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        rules = {row['id']: row for row in data['criteria']}
        self.assertEqual(rules['areas']['status'], 'not_met')
        self.assertEqual(rules['areas']['completed'], 6)
        self.assertEqual(rules['areas']['required'], 6)
        self.assertNotIn('제2외국어와 한문', rules['areas']['covered'])
        self.assertEqual(rules['areas']['missing'], ['제2외국어와 한문'])
        self.assertEqual(rules['total']['completed'], 24)
        self.assertEqual(len(data['courses']), len(courses))
        self.assertEqual(data['by_semester']['1-1'][-1]['code'], '002605')
        self.assertEqual(data['by_semester']['1-1'][-1]['credit'], 0)
        self.assertEqual(data['status'], 'needs_verification')
        self.assertIs(data['policy']['source_verified'], False)
        self.assertTrue(any('공식 최종본' in warning for warning in data['warnings']))

    def test_real_policy_zero_credit_advanced_course_does_not_fill_sw_slot(self):
        from .test_engine import zero_credit_sw_courses
        courses = zero_credit_sw_courses()
        self.transcript.confirm_courses({'courses': courses}, confirmed_by=self.user)
        response = self.client.get('/api/analysis/report/', {'transcript_id': self.transcript.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        rules = {row['id']: row for row in data['criteria']}
        self.assertEqual(rules['sw']['status'], 'not_met')
        self.assertEqual(rules['sw']['completed'], 9)
        self.assertEqual(rules['sw']['required'], 9)
        self.assertEqual(rules['sw']['slots_filled'], 2)
        self.assertTrue(rules['sw']['missing'])
        self.assertEqual(rules['total']['completed'], 9)
        self.assertEqual(len(data['courses']), len(courses))
        self.assertEqual(data['by_semester']['1-1'][0]['code'], '012305')
        self.assertEqual(data['by_semester']['1-1'][0]['credit'], 0)
        self.assertEqual(data['status'], 'needs_verification')
        self.assertIs(data['policy']['source_verified'], False)
        self.assertTrue(any('공식 최종본' in warning for warning in data['warnings']))

    def test_real_policy_additional_sources_survive_report_json(self):
        self.transcript.confirm_courses({'courses': []}, confirmed_by=self.user)
        response = self.client.get('/api/analysis/report/', {'transcript_id': self.transcript.id})
        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.json()['criteria'] if row['id'] == 'msc_designated')
        self.assertEqual(item.get('additional_sources'), [{'pdf_page': 98, 'printed_page': '공-10'}])
        self.assertEqual(item['source'], {'pdf_page': 10, 'printed_page': '8'})

    def test_unconfirmed_data_never_produces_a_graduation_report(self):
        response=self.client.get('/api/analysis/report/',{'transcript_id':self.transcript.id})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['status'],'needs_confirmation')

    def test_confirmed_document_has_track_specific_rules_and_page_provenance(self):
        self.transcript.confirm_courses({'courses':[{'code':'101810','name':'C-프로그래밍','credit':3,'grade':'A+','semester':'1-1','type':'MSC'}]},confirmed_by=self.user)
        response=self.client.get('/api/analysis/report/',{'transcript_id':self.transcript.id})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['status'],'needs_verification')
        self.assertEqual(response.data['policy']['accreditation_track'],'non_accredited')
        rules={r['id']:r for r in response.data['criteria']}
        self.assertEqual(rules['msc']['required'],23)
        self.assertEqual(rules['msc']['source']['pdf_page'],10)
        self.assertEqual(response.data['by_semester']['1-1'][0]['code'],'101810')

    def test_foreign_transcript_and_foreign_legacy_user_routes_are_denied(self):
        foreign=Transcript.objects.create(user=self.other)
        self.assertEqual(self.client.get('/api/analysis/report/',{'transcript_id':foreign.id}).status_code,404)
        self.assertEqual(self.client.get(f'/api/analysis/credit/total/{self.other.id}/').status_code,403)
        self.assertEqual(self.client.get(f'/api/semesters/courses/lists/{self.other.id}/').status_code,403)

    def test_missing_or_unknown_profile_never_selects_legacy_policy(self):
        self.user.accreditation_track=''
        self.user.save(update_fields=['accreditation_track'])
        response=self.client.get('/api/analysis/report/',{'transcript_id':self.transcript.id})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['status'],'profile_required')

    def test_corrupt_persisted_policy_is_unavailable_not_server_error(self):
        self.transcript.confirm_courses({'courses': []}, confirmed_by=self.user)
        spec = select_policy('컴퓨터공학과', 2025, 'non_accredited')
        row = RequirementRuleSet.objects.create(**spec)
        # Simulate legacy/corrupted data bypassing normal model validation.
        spec['data']['criteria'][0].pop('minimum')
        RequirementRuleSet.objects.filter(pk=row.pk).update(data=spec['data'])
        response = self.client.get('/api/analysis/report/', {'transcript_id': self.transcript.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'policy_unavailable')
        self.assertEqual(response.data['criteria'], [])
        self.assertTrue(response.data['warnings'])

    def test_credit_aggregate_overflow_is_controlled_before_json_rendering(self):
        from .test_engine import course
        self.transcript.confirm_courses({'courses': [course('101810', 1e308), course('012305', 1e308)]}, confirmed_by=self.user)
        response = self.client.get('/api/analysis/report/', {'transcript_id': self.transcript.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'needs_confirmation')
        self.assertEqual(response.data['criteria'], [])
        self.assertNotIn(b'Infinity', response.content)
