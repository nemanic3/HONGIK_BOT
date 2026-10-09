"""Transcript extraction tasks; structured drafts are never user confirmation."""
from celery import shared_task
from .models import Transcript


@shared_task
def process_transcript(transcript_id: int):
    from .reader import read_document
    from .parser import parse_course_pages
    try:
        transcript = Transcript.objects.get(pk=transcript_id)
    except Transcript.DoesNotExist:
        return None
    if transcript.confirmed_data is not None or transcript.ocr_raw_data is not None:
        return transcript.status
    claimed = Transcript.objects.filter(pk=transcript_id, confirmed_data__isnull=True,
                                        ocr_raw_data__isnull=True).exclude(status='processing').update(
                                            status=Transcript.STATUS.processing)
    if not claimed:
        transcript.refresh_from_db()
        return transcript.status
    try:
        raw = {'schema_version': 1, 'pages': [], 'warnings': []}
        for source in transcript.pages.order_by('page_number'):
            try:
                with source.file.open('rb') as file:
                    extracted = read_document(file)
            except Exception:
                message = 'Source extraction failed; original file preserved. Enter courses manually.'
                extracted = {'pages': [{'page_number': 1, 'text': '', 'error': message, 'method': 'failed'}],
                             'warnings': [{'code': 'extraction_failed', 'file_number': source.page_number, 'message': message}]}
            for page in extracted['pages']:
                raw['pages'].append({**page, 'file_number': source.page_number})
            raw['warnings'].extend(extracted['warnings'])
        try:
            document = parse_course_pages(raw)
        except Exception:
            document = {'schema_version': 1, 'courses': [], 'needs_review': True, 'incomplete': True,
                        'warnings': [{'code': 'parser_failed', 'message': 'Parsing failed; review raw text and enter courses manually.'}]}
        transcript.record_ocr_result(raw, courses=document)
        if not any(page.get('text', '').strip() for page in raw['pages']) and raw['warnings']:
            Transcript.objects.filter(pk=transcript_id, confirmed_data__isnull=True).update(
                status=Transcript.STATUS.error,
                error_message='No text extracted. Configure TRANSCRIPT_IMAGE_OCR_PROVIDER for scanned/image files, or enter courses manually. Original files preserved.')
    except Exception:
        Transcript.objects.filter(pk=transcript_id, confirmed_data__isnull=True).update(
            status=Transcript.STATUS.error,
            error_message='Transcript processing failed; original files preserved. Enter courses manually or upload a new transcript.')
    transcript.refresh_from_db()
    return transcript.status
