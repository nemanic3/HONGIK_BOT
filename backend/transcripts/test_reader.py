"""Generated fixtures are synthetic, never a student's transcript."""
from io import BytesIO
from django.test import SimpleTestCase
import pymupdf

HEADER = 'code | name | credit | grade | semester | type | major_field'
ROW = '001009 | English | 3 | A+ | 1-1 | General | Required'


def embedded_pdf(text=HEADER + '\n' + ROW):
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 40), text, fontsize=10)
        return doc.tobytes()


def configured_fixture_provider(data):
    return {'text': 'explicit test-provider fixture', 'provider': 'test_stub'}


class ReaderTests(SimpleTestCase):
    def test_setting_loads_pluggable_provider_for_images(self):
        from django.test import override_settings
        from PIL import Image
        from .reader import read_document
        image = BytesIO()
        Image.new('RGB', (200, 100), 'white').save(image, format='PNG')
        with override_settings(TRANSCRIPT_IMAGE_OCR_PROVIDER='transcripts.test_reader.configured_fixture_provider'):
            raw = read_document(BytesIO(image.getvalue()))
        self.assertEqual(raw['pages'][0]['text'], 'explicit test-provider fixture')
        self.assertEqual(raw['pages'][0]['provider'], 'test_stub')

    def test_image_provider_blocker_is_recorded_without_losing_pdf_text(self):
        from .reader import read_document
        with pymupdf.open(stream=embedded_pdf(), filetype='pdf') as doc:
            doc.new_page()
            mixed = doc.tobytes()
        def unavailable(_):
            raise RuntimeError('fixture provider unavailable')
        raw = read_document(BytesIO(mixed), image_provider=unavailable)
        self.assertIn(ROW, raw['pages'][0]['text'])
        self.assertEqual(raw['pages'][1]['text'], '')
        self.assertTrue(raw['pages'][1]['error'])
        self.assertTrue(raw['warnings'])

    def test_png_is_decoded_and_given_to_image_provider(self):
        from PIL import Image
        from .reader import read_document
        image = BytesIO()
        Image.new('RGB', (200, 100), 'white').save(image, format='PNG')
        raw = read_document(BytesIO(image.getvalue()), image_provider=lambda _: {
            'text': 'image fixture', 'provider': 'test_stub'})
        self.assertEqual(raw['pages'][0]['text'], 'image fixture')

    def test_embedded_pdf_extracts_real_text_without_image_provider(self):
        from .reader import read_document
        def forbidden(_):
            self.fail('Embedded text must not invoke image OCR')
        raw = read_document(BytesIO(embedded_pdf()), image_provider=forbidden)
        self.assertEqual(raw['pages'][0]['method'], 'pdf_text')
        self.assertIn(ROW, raw['pages'][0]['text'])
        self.assertEqual(raw['pages'][0]['page_number'], 1)
        self.assertEqual(raw['warnings'], [])

    def test_scanned_pdf_renders_page_for_pluggable_image_provider(self):
        from PIL import Image
        from .reader import read_document
        image = BytesIO()
        Image.new('RGB', (200, 100), 'white').save(image, format='PNG')
        with pymupdf.open() as doc:
            page = doc.new_page(width=200, height=100)
            page.insert_image(page.rect, stream=image.getvalue())
            scanned = doc.tobytes()
        captured = []
        def provider(data):
            captured.append(data)
            return {'text': 'provider fixture text', 'provider': 'test_stub'}
        raw = read_document(BytesIO(scanned), image_provider=provider)
        self.assertEqual(raw['pages'][0]['method'], 'image_ocr')
        self.assertEqual(raw['pages'][0]['text'], 'provider fixture text')
        self.assertEqual(raw['pages'][0]['provider'], 'test_stub')
        self.assertTrue(captured[0].startswith(b'\x89PNG'))
