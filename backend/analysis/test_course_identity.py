from copy import deepcopy
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import CourseIdentity, CourseVersion, CourseEvidence, CourseRelation
from .course_identity import catalog_snapshot, resolve_document, recognition_links
from .engine import evaluate_rules
from .test_engine import course, policy


class CourseIdentityTests(TestCase):
    def setUp(self):
        self.e = CourseEvidence.objects.create(document='SYNTHETIC official fixture', sha256='a'*64,
            pdf_page=1, printed_page='1', statement='Synthetic relationship only',
            official_verified=True, verified_by='test', verified_at=timezone.now())
        self.old = self.version('001001', 'Old', 2021)
        self.new = self.version('001002', 'New', 2026)
        self.spec = policy([{'id':'total','kind':'credits','minimum':6,'roles':['total']},
            {'id':'required','kind':'course_groups','groups':[['001002']]}],
            [{'code':'001002','name':'New','roles':['major']}])
        self.spec.update(curriculum_year=2026, version='synthetic-v1')

    def version(self, code, name, year, **extra):
        return CourseVersion.objects.create(course=CourseIdentity.objects.create(), code=code, name=name,
            academic_year=year, term='1', credit=3, classification='전필', evidence=self.e, **extra)

    def row(self, version, **extra):
        return course(version.code, name=version.name, semester=f'{version.academic_year}-{version.term}', type='전필', **extra)

    def snap(self):
        return catalog_snapshot('컴퓨터공학과')

    def relation(self, kind, **extra):
        return CourseRelation.objects.create(source=self.old, target=self.new, kind=kind, evidence=self.e, **extra)

    def result(self, rows):
        return evaluate_rules(self.spec, {'courses':rows}, course_catalog=self.snap())

    def test_exact_code_and_calendar_term_cross_checked(self):
        r=resolve_document({'courses':[self.row(self.old)]},self.snap())['courses'][0]
        self.assertEqual(r['identification']['status'],'matched')
        self.assertEqual(r['code'],'001001')
        for fields in ({'semester':'1-1'},{'semester':'2022-1'},{'name':'New'},{'credit':4},{'type':'전선'},
                       {'code':'999999'},{'academic_year':2022},{'semester':'2021-winter'},{'code':''}):
            row={**self.row(self.old), **fields}
            out=resolve_document({'courses':[row]},self.snap())['courses'][0]
            self.assertEqual(out['identification']['status'],'needs_review',fields)
            self.assertIsNone(out['identification']['course_id'])
            self.assertEqual(out['name'],row['name'])

    def test_ambiguous_code_same_term_never_auto_selected(self):
        self.version('001001','Other',2021)
        r=resolve_document({'courses':[self.row(self.old)]},self.snap())['courses'][0]
        self.assertEqual(len(r['identification']['candidates']),2)
        self.assertIsNone(r['identification']['version_id'])

    def test_unverified_relation_does_not_merge_or_satisfy(self):
        draft=CourseEvidence.objects.create(document='draft',sha256='b'*64,pdf_page=4,printed_page='2',statement='unverified')
        CourseRelation.objects.create(source=self.old,target=self.new,kind='same_course',evidence=draft)
        r=self.result([self.row(self.old)])
        self.assertEqual(r['criteria'][1]['completed'],0)
        self.assertEqual(r['courses'][0]['identity'],str(self.old.course_id))

    def test_verified_same_course_satisfies_and_prevents_double_credit(self):
        self.relation('same_course')
        r=self.result([self.row(self.old)])
        self.assertEqual(r['criteria'][1]['completed'],1)
        self.assertEqual(r['courses'][0]['code'],'001001')
        r=self.result([self.row(self.old),self.row(self.new)])
        self.assertEqual(r['criteria'][0]['completed'],0)
        self.assertEqual(len(r['courses']),2)

    def test_replacement_is_scoped_directional_and_counts_distinct_credits(self):
        self.relation('replacement', policy_version='synthetic-v1', criterion_id='required')
        r=self.result([self.row(self.old),self.row(self.new)])
        self.assertEqual(r['criteria'][0]['completed'],6)
        self.assertNotEqual(r['courses'][0]['identity'],r['courses'][1]['identity'])
        self.assertEqual(self.result([self.row(self.old)])['criteria'][1]['completed'],1)
        self.spec['version']='different'
        self.assertEqual(self.result([self.row(self.old)])['criteria'][1]['completed'],0)

    def test_retake_permission_not_requirement_equivalence(self):
        self.relation('retake')
        self.assertEqual(self.result([self.row(self.old)])['criteria'][1]['completed'],0)
        r=self.result([self.row(self.old,credit_decision='include'),self.row(self.new,credit_decision='include')])
        self.assertEqual(r['criteria'][0]['completed'],0)
        r=self.result([self.row(self.old,credit_decision='exclude'),self.row(self.new,credit_decision='include')])
        self.assertEqual(r['criteria'][0]['completed'],3)

    def test_client_identity_is_ignored_and_edit_recomputed(self):
        row=self.row(self.old, identification={'status':'matched','version_id':self.new.pk,'course_id':str(self.new.course_id)})
        r=self.result([row])
        self.assertEqual(r['criteria'][1]['completed'],0)
        self.assertEqual(r['courses'][0]['identification']['version_id'],self.old.pk)

    def test_changed_attributes_cannot_silently_share_id(self):
        with self.assertRaises(ValidationError):
            CourseVersion.objects.create(course=self.old.course,code='NEW',name='Changed',academic_year=2022,
                term='1',credit=4,classification='전선',evidence=self.e)
        self.old.name='Changed'
        with self.assertRaises(ValidationError): self.old.save()

    def test_same_code_reused_for_unrelated_course_stays_distinct(self):
        other=self.version('001001','Unrelated',2026)
        r=self.result([self.row(self.old),self.row(other)])
        self.assertNotEqual(r['courses'][0]['identity'],r['courses'][1]['identity'])
        self.assertEqual(r['criteria'][0]['completed'],6)

    def test_no_history_preserves_values_but_never_proves_completion(self):
        rows=[course('001002',2.5,name='Historical',semester='1-1')]
        original=deepcopy(rows)
        r=self.result(rows)
        self.assertEqual(r['criteria'][0]['completed'],2.5)
        self.assertEqual(r['criteria'][1]['completed'],0)
        self.assertEqual(r['status'],'needs_verification')
        self.assertEqual(rows,original)

    def test_verified_evidence_requires_audit(self):
        self.e.verified_by=''
        with self.assertRaises(ValidationError): self.e.save()

    def test_legacy_relation_needs_explicit_official_verification(self):
        self.spec['data']['course_relations']=[{'kind':'same_course','from_code':'001001','to_code':'001002',
            'source_document':'draft','source':{'pdf_page':4,'printed_page':'2'}}]
        r=evaluate_rules(self.spec,{'courses':[self.row(self.old)]})
        self.assertEqual(r['criteria'][1]['completed'],0)

    def test_pdf_draft_cannot_verify_course_even_with_verified_relation(self):
        self.relation('same_course')
        self.e.official_verified=False
        self.e.save()
        r=self.result([self.row(self.old)])
        self.assertEqual(r['courses'][0]['identification']['status'],'needs_review')
        self.assertEqual(r['criteria'][1]['completed'],0)

    def test_partial_matching_same_code_does_not_double_count(self):
        r=self.result([self.row(self.new),{**self.row(self.new),'credit':4,'semester':'2025-1'}])
        self.assertEqual(r['criteria'][0]['completed'],0)

    def test_scope_other_department_does_not_match(self):
        out=resolve_document({'courses':[self.row(self.old)]},catalog_snapshot('다른학과'))
        self.assertIsNone(out['courses'][0]['identification']['version_id'])

    def test_same_identity_with_unchanged_official_term_information(self):
        v=CourseVersion.objects.create(course=self.old.course,code=self.old.code,name=self.old.name,
            academic_year=2026,term='1',credit=3,classification='전필',evidence=self.e)
        r=self.result([self.row(self.old),self.row(v)])
        self.assertEqual(r['criteria'][0]['completed'],0)

    def test_relation_and_versions_require_explicit_valid_scope(self):
        with self.assertRaises(ValidationError): self.relation('replacement')
        with self.assertRaises(ValidationError): self.relation('retake',criterion_id='required')
        with self.assertRaises(ValidationError):
            CourseRelation.objects.create(source=self.old,target=self.old,kind='same_course',evidence=self.e)

    def test_api_recomputes_confirmation_and_get_preserves_stored_json(self):
        from users.models import User
        from transcripts.models import Transcript
        from rest_framework.test import APIClient
        user=User.objects.create(username='Tidentity',student_id='Tidentity',major='컴퓨터공학과',
            admission_year=2021,accreditation_track='non_accredited')
        other=User.objects.create(username='Totherid',student_id='Totherid')
        t=Transcript.objects.create(user=user)
        client=APIClient(); client.force_authenticate(user)
        doc={'schema_version':1,'courses':[self.row(self.old,identification={'status':'matched','version_id':self.new.pk})]}
        response=client.post(f'/api/transcripts/confirm/{t.pk}/',doc,format='json')
        self.assertEqual(response.status_code,200)
        t.refresh_from_db()
        self.assertEqual(t.confirmed_data['courses'][0]['identification']['version_id'],self.old.pk)
        saved=deepcopy(t.confirmed_data)
        self.e.official_verified=False; self.e.save()
        response=client.get(f'/api/transcripts/detail/{t.pk}/')
        self.assertEqual(response.data['document']['courses'][0]['identification']['status'],'needs_review')
        t.refresh_from_db(); self.assertEqual(t.confirmed_data,saved)
        doc['courses'][0]['code']='UNKNOWN'
        response=client.post(f'/api/transcripts/confirm/{t.pk}/',doc,format='json')
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.data['document']['courses'][0]['identification']['version_id'])
        self.assertEqual(client.get('/api/analysis/report/',{'transcript_id':t.pk}).data['status'],'needs_verification')
        client.force_authenticate(other)
        self.assertEqual(client.get(f'/api/transcripts/detail/{t.pk}/').status_code,404)
        self.assertEqual(client.post(f'/api/transcripts/confirm/{t.pk}/',doc,format='json').status_code,404)
