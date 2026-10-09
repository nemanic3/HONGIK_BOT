# Transcript upload, review and confirmation API

All routes require the existing JWT authentication. No routes return storage URLs or server paths. Tests and the extraction probe use synthetic fixtures and isolated storage/database only.

## Frontend contract

- `POST /api/transcripts/{user_id}/` — multipart repeated **files**, 1–5 PDF/JPG/JPEG/PNG files, combined maximum **5 MiB**. Signature, matching extension and decoder validation required. Encrypted/empty/>50-page PDFs, animated images, and >20-megapixel pages are rejected with 400. Ownership mismatch: 403.
- `GET /api/transcripts/status/{user_id}/` — latest resource summary, 404 if absent; ownership mismatch: 403.
- `GET /api/transcripts/detail/{transcript_id}/` — owner's resource with raw extraction and selected document. Non-owner/missing: 404. GET never changes data.
- `POST /api/transcripts/confirm/{transcript_id}/` — JSON document **directly**, not wrapped: `{"schema_version":1,"courses":[...]}`. Uses existing `confirm_courses`. Non-owner/missing: 404; invalid document: 400; GET: 405. Success: 200 with updated detail. Empty courses explicitly confirmed by the owner are allowed.
- Existing `GET /api/transcripts/parsed/{user_id}/` is preserved as a compatibility endpoint; new clients should use detail instead.

Summary fields: `id`, `transcript_id` (same resource ID), `status`, `error_message`, `source`, `needs_review`.

Detail adds: `ocr_raw_data`, `document`, `confirmed_at` (ISO datetime or null).

`source`: **confirmed > ocr > raw > legacy > none**. `needs_review` remains true until manual confirmation, including a fully populated OCR draft. Confirmed data is authoritative even when empty.

Courses: `code` string (leading zeros preserved), `name` string, `credit` nonnegative finite number, `grade` string, `semester` string, `type` string, `major_field` string; schema also supports `retake`, `academic_year`, `term`, `aliases`. Confirmation requires nonblank name/grade/semester/type and a numeric credit. Missing optional code/major_field may remain blank. No academic categorization, retake or graduation policy is inferred.

Draft metadata: `needs_review`, `incomplete`, `warnings`, `unparsed_lines`; nullable/missing course values are allowed only in drafts. Unknown layouts produce an empty **review draft**, not a zero-credit analysis. Flagged drafts are rejected by `get_analysis_document()` until confirmed. Parser failure preserves raw text and returns a warning-bearing incomplete draft.

Raw structure: `{"schema_version":1,"pages":[{"file_number":1,"page_number":1,"method":"pdf_text","text":"..."}],"warnings":[]}`. Methods include `pdf_text`, `image_ocr`, `failed`. Raw provider metadata and text remain separate from confirmed values.

## Processing and real limitations

Install OCR decoding dependencies into the existing isolated backend venv:

```sh
.venv/bin/python -m pip install -r requirements-ocr.txt
```

Default **TRANSCRIPT_PROCESSING=celery** publishes work to the configured broker. Upload returns **201** with the actual persisted state (normally `pending`, never fake `processing`). Broker failure returns actionable **503**, with `transcript_id`, persisted `error`, and uploaded files retained. Successful publishing cannot prove a worker is running; the client should poll status.

Explicit local mode:

```sh
TRANSCRIPT_PROCESSING=inline .venv/bin/python manage.py runserver
```

Inline upload returns **201** with final persisted status (`done` or `error`). `done` means extraction/parse attempt completed; it does **not** mean reviewed or graduation-eligible.

PyMuPDF reads genuine embedded PDF text without invoking image OCR. Scanned PDF pages are rendered to PNG and images are decoded to PNG before the provider seam. No Paddle module is imported by this path.

Image OCR is optional and deliberately **not fabricated**: set `TRANSCRIPT_IMAGE_OCR_PROVIDER=your.module.callable` to a trusted dotted callable accepting PNG bytes and returning `{"text":"...","provider":"actual-provider-name"}` (extra JSON metadata optional). Providers must impose timeouts and operate locally or under an explicitly approved privacy policy. Without a provider, images/scans produce `ocr_failed` warnings, empty raw page text, and actionable `error` if no text could be extracted. Manual confirmation still works. Partial extraction preserves available text and valid draft rows and remains review-only.

Current machine has no tesseract or Redis server. Optional native macOS OCR is now available via the trusted local callable below; this does not change the default provider or processing mode. Provider-stub tests remain seam regressions, **not evidence of OCR accuracy**.

### Optional local Apple Vision provider (macOS)

```sh
TRANSCRIPT_IMAGE_OCR_PROVIDER=transcripts.vision_provider.recognize_png \
TRANSCRIPT_PROCESSING=inline .venv/bin/python manage.py runserver
# Generated, labeled non-student fixture; runs real Swift/Vision on macOS:
.venv/bin/python -m unittest transcripts.test_vision_provider -v
```

Requires macOS, Apple Swift command-line tools on `PATH`, and the existing Pillow dependency. PNG bytes go to `VNRecognizeTextRequest` with `.accurate`, language correction disabled, and requested `ko-KR`/`en-US`. Result metadata records requested/supported/selected/unsupported languages, request revision, and `unsupported_recognition_language` warnings when falling back to the supported subset. No supported requested language, no recognized text, missing platform/tools, timeout, or invalid output is an explicit blocker; the existing reader records `ocr_failed` and preserves manual correction.

The adapter runs an argv subprocess without a shell, with a 90-second timeout, a private temporary directory honoring `TMPDIR`, a private PNG file, and cleanup on success/failure. Limits: 10 MiB input, 20 megapixels, 1 MiB returned JSON, and 1024 diagnostic bytes. Captured process streams use private temporary files rather than unbounded in-memory pipes. The Swift module cache is temporary too; compilation adds per-page latency. No external OCR service or automatic provider enablement is added.

Real execution recognized the generated English label/course text and Korean `컴퓨터 공학 3 A+` on this machine (Swift 6.3.3, Vision revision 3). A real Swift language-selection probe verifies English-only fallback and a blocker when neither requested language is supported. These clean synthetic examples do **not** establish transcript/layout accuracy; every OCR result remains review-only.

Retries do not rerun or overwrite an archived raw extraction or a confirmed resource. Conditional task status writes and locked model writes protect confirmation made during processing. Original files and legacy/raw JSON remain intact. A crashed worker left in `processing` is not automatically reclaimed; operator inspection/new upload is required rather than unsafe concurrent overwrites.

## Verification

```sh
.venv/bin/python manage.py test
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python scripts/verify_transcript_extraction.py
```

No transcript schema migration is needed for this implementation. Do not migrate or change the original `db.sqlite3` during verification; Django tests use their separate test database.
