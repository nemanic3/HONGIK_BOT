"""Task integration uses isolated storage/database and real synthetic PDFs."""
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from users.models import User
from .models import Transcript, TranscriptPage
from .test_reader import embedded_pdf, ROW


class PipelineTaskTests(TestCase):
    def setUp(self):
        self.storage = TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.storage.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create(username='T600001', student_id='T600001', full_name='Fixture')

    def create_transcript(self, data=None):
        transcript = Transcript.objects.create(user=self.user)
        TranscriptPage.objects.create(transcript=transcript, page_number=1,
            file=SimpleUploadedFile('synthetic-fixture.pdf', data or embedded_pdf(), content_type='application/pdf'))
        return transcript

    def test_partial_source_failure_retains_prior_extraction(self):
        from .tasks import process_transcript
        from .reader import read_document
        transcript = self.create_transcript()
        TranscriptPage.objects.create(transcript=transcript, page_number=2,
            file=SimpleUploadedFile('synthetic-second.pdf', embedded_pdf()))
        raw = read_document(__import__('io').BytesIO(embedded_pdf()))
        with patch('transcripts.reader.read_document', side_effect=[raw, RuntimeError('fixture read failure')]):
            result = process_transcript.run(transcript.id)
        transcript.refresh_from_db()
        self.assertEqual(result, 'done')
        self.assertIn(ROW, transcript.ocr_raw_data['pages'][0]['text'])
        self.assertTrue(transcript.ocr_raw_data['pages'][1]['error'])
        self.assertTrue(transcript.ocr_data['warnings'])
        self.assertTrue(transcript.ocr_data['incomplete'])

    @override_settings(TRANSCRIPT_IMAGE_OCR_PROVIDER='')
    def test_real_png_without_provider_reports_blocker_preserving_raw(self):
        from io import BytesIO
        from PIL import Image
        from .tasks import process_transcript
        image = BytesIO()
        Image.new('RGB', (200, 100), 'white').save(image, format='PNG')
        transcript = Transcript.objects.create(user=self.user)
        TranscriptPage.objects.create(transcript=transcript, page_number=1,
            file=SimpleUploadedFile('synthetic-image.png', image.getvalue()))
        result = process_transcript.run(transcript.id)
        transcript.refresh_from_db()
        self.assertEqual(result, 'error')
        self.assertTrue(transcript.error_message)
        self.assertEqual(transcript.ocr_raw_data['pages'][0]['text'], '')
        self.assertTrue(transcript.ocr_data['warnings'])
        self.assertIsNone(transcript.get_analysis_document())

    def test_parser_failure_preserves_raw_and_returns_review_draft(self):
        from .tasks import process_transcript
        transcript = self.create_transcript()
        with patch('transcripts.parser.parse_course_pages', side_effect=RuntimeError('fixture failure')):
            result = process_transcript.run(transcript.id)
        transcript.refresh_from_db()
        self.assertEqual(result, 'done')
        self.assertIn(ROW, transcript.ocr_raw_data['pages'][0]['text'])
        self.assertEqual(transcript.ocr_data['courses'], [])
        self.assertTrue(transcript.ocr_data['incomplete'])
        self.assertTrue(transcript.ocr_data['warnings'])
        self.assertIsNone(transcript.get_analysis_document())

    def test_worker_failure_after_confirmation_does_not_change_any_field(self):
        from .tasks import process_transcript
        transcript = self.create_transcript()
        saved = {}
        def confirm_then_fail(_):
            transcript.confirm_courses({'courses': []}, confirmed_by=self.user)
            saved.update(Transcript.objects.filter(pk=transcript.pk).values().get())
            raise RuntimeError('fixture provider failure after confirmation')
        with patch('transcripts.reader.read_document', side_effect=confirm_then_fail):
            process_transcript.run(transcript.id)
        self.assertEqual(Transcript.objects.filter(pk=transcript.pk).values().get(), saved)

    def test_successful_retry_does_not_change_draft_or_raw(self):
        from .tasks import process_transcript
        transcript = self.create_transcript()
        process_transcript.run(transcript.id)
        before = Transcript.objects.filter(pk=transcript.pk).values().get()
        with patch('transcripts.reader.read_document', side_effect=AssertionError('must not run again')):
            process_transcript.run(transcript.id)
        self.assertEqual(Transcript.objects.filter(pk=transcript.pk).values().get(), before)

    def test_task_persists_embedded_text_and_structured_draft(self):
        from .tasks import process_transcript
        transcript = self.create_transcript()
        result = process_transcript.run(transcript.id)
        transcript.refresh_from_db()
        self.assertEqual(result, 'done')
        self.assertIn(ROW, transcript.ocr_raw_data['pages'][0]['text'])
        self.assertEqual(transcript.ocr_data['courses'][0]['code'], '001009')
        self.assertTrue(transcript.ocr_data['needs_review'])
        self.assertIsNone(transcript.confirmed_data)
