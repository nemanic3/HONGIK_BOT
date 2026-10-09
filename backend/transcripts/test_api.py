"""Authenticated multipart -> real extraction -> draft -> manual confirmation."""
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from users.models import User
from .models import Transcript
from .test_reader import embedded_pdf, ROW


class TranscriptAPITests(TestCase):
    def setUp(self):
        storage = TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        settings = override_settings(MEDIA_ROOT=storage.name, TRANSCRIPT_PROCESSING='inline')
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = User.objects.create(username='T700001', student_id='T700001', full_name='Fixture')
        self.other = User.objects.create(username='T700002', student_id='T700002', full_name='Other')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def upload(self, data=None, name='synthetic-fixture.pdf'):
        return self.client.post(f'/api/transcripts/{self.user.id}/', {'files': [
            SimpleUploadedFile(name, data if data is not None else embedded_pdf())]}, format='multipart')

    @override_settings(TRANSCRIPT_PROCESSING='celery')
    def test_queue_failure_preserves_upload_and_reports_actionable_503(self):
        with patch('transcripts.tasks.process_transcript.delay', side_effect=ConnectionError('/private/server/path')):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['status'], 'error')
        transcript = Transcript.objects.get(pk=response.data['transcript_id'])
        self.assertEqual(transcript.status, 'error')
        with transcript.pages.get().file.open('rb') as file:
            self.assertTrue(file.read().startswith(b'%PDF-'))
        self.assertNotIn('/private', str(response.data))
        self.assertIn('queue', response.data['error_message'].lower())

    @override_settings(TRANSCRIPT_PROCESSING='celery')
    def test_enqueued_upload_returns_persisted_pending_not_fake_processing(self):
        with patch('transcripts.tasks.process_transcript.delay', return_value=None):
            response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(Transcript.objects.get(pk=response.data['id']).status, 'pending')

    def test_confirmation_of_raw_or_failed_upload_is_manual_and_marks_done(self):
        transcript = Transcript.objects.create(user=self.user, status='error', error_message='fixture blocker',
                                               ocr_raw_data={'pages': [{'text': 'unknown fixture'}]})
        response = self.client.post(f'/api/transcripts/confirm/{transcript.id}/', {
            'schema_version': 1, 'courses': [{'code': '001009', 'name': 'English', 'credit': 3,
                'grade': 'A+', 'semester': '1-1', 'type': 'General', 'major_field': 'Required'}]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'done')
        self.assertIsNone(response.data['error_message'])
        self.assertFalse(response.data['needs_review'])
        self.assertEqual(response.data['ocr_raw_data']['pages'][0]['text'], 'unknown fixture')

    def test_ownership_and_authentication_cover_all_resource_endpoints(self):
        transcript = Transcript.objects.create(user=self.other)
        for method, url in [('get', f'/api/transcripts/detail/{transcript.id}/'),
                            ('post', f'/api/transcripts/confirm/{transcript.id}/'),
                            ('get', f'/api/transcripts/status/{self.other.id}/'),
                            ('get', f'/api/transcripts/parsed/{self.other.id}/'),
                            ('post', f'/api/transcripts/{self.other.id}/')]:
            with self.subTest(url=url):
                self.assertIn(getattr(self.client, method)(url).status_code, (403, 404))
        self.client.force_authenticate(user=None)
        for url in [f'/api/transcripts/detail/{transcript.id}/', f'/api/transcripts/confirm/{transcript.id}/']:
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_invalid_confirmation_and_get_never_edit(self):
        transcript = Transcript.objects.create(user=self.user)
        before = Transcript.objects.filter(pk=transcript.id).values().get()
        url = f'/api/transcripts/confirm/{transcript.id}/'
        invalid = [{}, {'courses': []}, {'schema_version': True, 'courses': []},
                   {'schema_version': 2, 'courses': []}, {'schema_version': 1, 'courses': 'not list'},
                   {'schema_version': 1, 'courses': [{'name': 'missing fields'}]},
                   {'schema_version': 1, 'courses': [{'name': 'English', 'credit': -3}]}]
        for document in invalid:
            with self.subTest(document=document):
                self.assertEqual(self.client.post(url, document, format='json').status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(f'/api/transcripts/detail/{transcript.id}/', {}, format='json').status_code, 405)
        self.assertEqual(Transcript.objects.filter(pk=transcript.id).values().get(), before)

    def test_invalid_uploads_rejected_before_storage(self):
        for data, name in [(b'not pdf', 'fake.pdf'), (b'%PDF-1.7\nnot valid', 'broken.pdf'),
                           (b'\x89PNG\r\n\x1a\ninvalid', 'broken.png'),
                           (embedded_pdf(), 'transcript.exe')]:
            with self.subTest(name=name):
                response = self.upload(data, name)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Transcript.objects.count(), 0)

    def test_combined_size_and_file_count_are_bounded(self):
        response = self.upload(b'X' * (5 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 400)
        files = [SimpleUploadedFile(f'fixture-{i}.pdf', embedded_pdf()) for i in range(6)]
        response = self.client.post(f'/api/transcripts/{self.user.id}/', {'files': files}, format='multipart')
        self.assertEqual(response.status_code, 400)
        files = [SimpleUploadedFile(f'fixture-{i}.pdf', embedded_pdf() + b' ' * (3 * 1024 * 1024)) for i in range(2)]
        response = self.client.post(f'/api/transcripts/{self.user.id}/', {'files': files}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Transcript.objects.count(), 0)

    def test_embedded_pdf_upload_draft_correction_confirmation(self):
        with patch('transcripts.tasks.process_transcript.delay', return_value=None):
            response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.assertIn('transcript_id', response.data)
        tid = response.data['transcript_id']
        self.assertEqual(response.data['id'], tid)
        self.assertEqual(response.data['status'], 'done')
        detail = self.client.get(f'/api/transcripts/detail/{tid}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['source'], 'ocr')
        self.assertTrue(detail.data['needs_review'])
        self.assertIn(ROW, detail.data['ocr_raw_data']['pages'][0]['text'])
        course = dict(detail.data['document']['courses'][0], name='Corrected English', credit=2.5)
        confirmed = self.client.post(f'/api/transcripts/confirm/{tid}/', {
            'schema_version': 1, 'courses': [course]}, format='json')
        self.assertEqual(confirmed.status_code, 200)
        after = self.client.get(f'/api/transcripts/detail/{tid}/')
        self.assertEqual(after.data['source'], 'confirmed')
        self.assertFalse(after.data['needs_review'])
        self.assertEqual(after.data['document']['courses'][0]['credit'], 2.5)
        self.assertEqual(after.data['ocr_raw_data'], detail.data['ocr_raw_data'])
        self.assertTrue(after.data['confirmed_at'])
        transcript = Transcript.objects.get(pk=tid)
        self.assertEqual(transcript.ocr_data['courses'][0]['credit'], 3)
        self.assertEqual(transcript.confirmed_by_id, self.user.id)
        latest = self.client.get(f'/api/transcripts/status/{self.user.id}/')
        self.assertEqual(latest.data['transcript_id'], tid)
        self.assertEqual(latest.data['source'], 'confirmed')
