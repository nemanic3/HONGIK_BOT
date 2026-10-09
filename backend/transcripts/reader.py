"""Source-aware extraction. Embedded PDF text is not OCR.

Providers receive PNG bytes and return {text, provider, ...}; failures are real
review blockers, not invented text. Original files stay in private storage.
"""
from io import BytesIO
import pymupdf
from PIL import Image


def read_document(file, *, image_provider=None):
    data = file.read()
    pages, warnings = [], []

    def image_page(data, number):
        try:
            provider = image_provider
            if provider is None:
                from django.conf import settings
                from django.utils.module_loading import import_string
                path = getattr(settings, 'TRANSCRIPT_IMAGE_OCR_PROVIDER', '')
                if not path:
                    raise RuntimeError('No image OCR provider configured')
                provider = import_string(path)
            result = provider(data)
            if not isinstance(result, dict) or not isinstance(result.get('text'), str):
                raise ValueError('Invalid provider response')
            return {'page_number': number, **result, 'method': 'image_ocr'}
        except Exception:
            message = 'Image OCR unavailable or failed; configure an OCR provider or enter courses manually.'
            warnings.append({'page_number': number, 'code': 'ocr_failed', 'message': message})
            return {'page_number': number, 'method': 'image_ocr', 'text': '', 'error': message}

    if data.startswith(b'%PDF-'):
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            for number, page in enumerate(doc, 1):
                text = page.get_text(sort=True)
                if text.strip():
                    pages.append({'page_number': number, 'method': 'pdf_text', 'text': text})
                else:
                    pages.append(image_page(page.get_pixmap(dpi=200).tobytes('png'), number))
    else:
        with Image.open(BytesIO(data)) as image:
            output = BytesIO()
            image.convert('RGB').save(output, format='PNG')
            pages.append(image_page(output.getvalue(), 1))
    return {'schema_version': 1, 'pages': pages, 'warnings': warnings}
