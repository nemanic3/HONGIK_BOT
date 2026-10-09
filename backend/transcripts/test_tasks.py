"""Original provider-stub regressions, adapted to the source-aware reader seam."""
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from users.models import User
from .models import Transcript, TranscriptPage
from .test_reader import embedded_pdf


class OCRStorageTaskTests(TestCase):
    def setUp(self):
        storage = TemporaryDirectory()
        self.addCleanup(storage.cleanup)
        settings = override_settings(MEDIA_ROOT=storage.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def test_confirmed_task_retry_is_non_mutating(self):
        from .tasks import process_transcript
        user = User.objects.create(username='T500002', student_id='T500002', full_name='테스트')
        transcript = Transcript.objects.create(user=user, status='done')
        transcript.confirm_courses({'courses': []}, confirmed_by=user)
        before = Transcript.objects.filter(pk=transcript.pk).values().get()
        with patch('transcripts.reader.read_document', side_effect=AssertionError('confirmed retry must not read files')):
            process_transcript.run(transcript.id)
        self.assertEqual(Transcript.objects.filter(pk=transcript.pk).values().get(), before)

    def test_task_archives_raw_rows_without_inventing_structured_courses(self):
        from .tasks import process_transcript
        user = User.objects.create(username='T500001', student_id='T500001', full_name='테스트')
        transcript = Transcript.objects.create(user=user)
        TranscriptPage.objects.create(transcript=transcript, page_number=1,
            file=SimpleUploadedFile('synthetic-fixture.pdf', embedded_pdf()))
        rows = [['001009', '영어', '3']]
        raw = {'schema_version': 1, 'pages': [{'page_number': 1, 'method': 'provider_stub',
               'text': '001009 영어 3', 'rows': rows}], 'warnings': []}
        # Only extraction is substituted; task/parser/model/storage/DB are real.
        with patch('transcripts.reader.read_document', return_value=raw):
            result = process_transcript.run(transcript.id)
        transcript.refresh_from_db()
        self.assertEqual(result, 'done')
        self.assertEqual(transcript.ocr_raw_data['pages'][0]['rows'], rows)
        self.assertEqual(transcript.parsed_data, transcript.ocr_raw_data)
        self.assertEqual(transcript.ocr_data['courses'], [])
        self.assertTrue(transcript.ocr_data['incomplete'])
        self.assertIsNone(transcript.get_analysis_document())
        self.assertIsNone(transcript.confirmed_data)
