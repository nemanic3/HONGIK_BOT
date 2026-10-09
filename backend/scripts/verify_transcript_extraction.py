"""Real decoder/extractor probe using labeled synthetic fixtures, never the DB."""
import json
from io import BytesIO
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
from PIL import Image
from transcripts.reader import read_document
from transcripts.parser import parse_course_pages

HEADER = 'code | name | credit | grade | semester | type | major_field'
ROW = '001009 | English | 3 | A+ | 1-1 | General | Required'


def main():
    with tempfile.TemporaryDirectory(prefix='transcript-synthetic-probe-') as directory:
        pdf_path = Path(directory) / 'synthetic-fixture.pdf'
        with pymupdf.open() as pdf:
            page = pdf.new_page()
            page.insert_text((30, 40), HEADER + '\n' + ROW, fontsize=10)
            pdf.save(pdf_path)
        with pdf_path.open('rb') as file:
            raw = read_document(file)
        draft = parse_course_pages(raw)
        assert raw['pages'][0]['method'] == 'pdf_text'
        assert ROW in raw['pages'][0]['text']
        assert draft['courses'][0]['code'] == '001009'
        assert draft['courses'][0]['credit'] == 3
        image = BytesIO()
        Image.new('RGB', (200, 100), 'white').save(image, format='PNG')
        from django.conf import settings
        if not settings.configured:
            settings.configure(TRANSCRIPT_IMAGE_OCR_PROVIDER='')
        blocked = read_document(BytesIO(image.getvalue()))
        assert blocked['pages'][0]['text'] == ''
        assert blocked['warnings'][0]['code'] == 'ocr_failed'
        print(json.dumps({'fixture': 'synthetic / not student data', 'pdf_pages': len(raw['pages']),
                          'method': raw['pages'][0]['method'], 'courses': len(draft['courses']),
                          'code': draft['courses'][0]['code'], 'credit': draft['courses'][0]['credit'],
                          'needs_review': draft['needs_review'],
                          'image_ocr': 'NOT RUN: no real provider configured; blocker propagation verified'}, indent=2))


if __name__ == '__main__':
    main()
