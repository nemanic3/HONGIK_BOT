from copy import deepcopy

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from common.course_schema import CourseSchemaError, normalize_course_document


class Transcript(models.Model):
    class STATUS(models.TextChoices):
        pending = 'pending', '대기'
        processing = 'processing', '처리 중'
        done = 'done', '완료'
        error = 'error', '오류'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transcripts'
    )
    file = models.FileField(upload_to='transcripts/')
    status = models.CharField(
        max_length=10,
        choices=STATUS.choices,
        default=STATUS.pending
    )
    parsed_data = models.JSONField(null=True, blank=True)  # Legacy buffer: retained for compatibility.
    ocr_raw_data = models.JSONField(null=True, blank=True, editable=False)
    ocr_data = models.JSONField(null=True, blank=True)
    confirmed_data = models.JSONField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="confirmed_transcripts",
    )
    legacy_status = models.CharField(max_length=10, null=True, blank=True, editable=False)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        try:
            if self.ocr_data is not None:
                self.ocr_data = normalize_course_document(self.ocr_data)
            if self.confirmed_data is not None:
                self.confirmed_data = normalize_course_document(
                    self.confirmed_data, for_confirmation=True
                )
                if self.confirmed_at is None or self.confirmed_by_id != self.user_id:
                    raise ValidationError("확정 시각과 성적표 소유자의 확인이 필요합니다.")
            elif self.confirmed_at is not None or self.confirmed_by_id is not None:
                raise ValidationError("확정 데이터 없이 확인 정보를 저장할 수 없습니다.")
        except CourseSchemaError as exc:
            raise ValidationError(str(exc)) from exc

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        document_fields = {"ocr_data", "confirmed_data", "confirmed_at", "confirmed_by"}
        if update_fields is None or document_fields.intersection(update_fields):
            self.clean()
        super().save(*args, **kwargs)

    def get_course_document(self):
        """Confirmed > structured OCR > legacy. Empty confirmed data is authoritative."""
        for data in (self.confirmed_data, self.ocr_data, self.parsed_data):
            if data is not None:
                try:
                    return normalize_course_document(data)
                except CourseSchemaError:
                    # Do not silently fall back from an invalid authoritative source.
                    return None
        return None

    def get_analysis_document(self):
        document = self.get_course_document()
        if document is None:
            return None
        if self.confirmed_data is None and (document.get('needs_review') or document.get('incomplete')):
            return None
        try:
            return normalize_course_document(document, for_confirmation=True)
        except CourseSchemaError:
            return None

    def record_ocr_result(self, raw_data, *, courses=None):
        """Store raw output separately. Never turn table cells into guessed courses."""
        try:
            document = normalize_course_document(raw_data if courses is None else courses)
        except CourseSchemaError as exc:
            if courses is not None:
                raise ValidationError(str(exc)) from exc
            document = None
        with transaction.atomic(using=self._state.db):
            stored = type(self).objects.select_for_update().get(pk=self.pk)
            if stored.confirmed_data is not None:
                raise ValidationError("확정된 성적표의 OCR 원본은 덮어쓸 수 없습니다.")
            if stored.ocr_raw_data is not None and stored.ocr_raw_data != raw_data:
                raise ValidationError("기존 OCR 원본은 보존해야 합니다. 새 성적표를 생성하세요.")
            stored.ocr_raw_data = deepcopy(raw_data)
            if stored.parsed_data is None:
                stored.parsed_data = deepcopy(raw_data)
            if document is not None or stored.ocr_data is None:
                stored.ocr_data = document
            stored.status = self.STATUS.done
            stored.error_message = None
            stored.save(update_fields=["ocr_raw_data", "ocr_data", "parsed_data", "status", "error_message", "updated_at"])
        self.refresh_from_db()

    def confirm_courses(self, data, *, confirmed_by):
        try:
            document = normalize_course_document(data, for_confirmation=True)
        except CourseSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        with transaction.atomic(using=self._state.db):
            stored = type(self).objects.select_for_update().get(pk=self.pk)
            if confirmed_by.pk != stored.user_id:
                raise ValidationError("성적표 소유자만 데이터를 확정할 수 있습니다.")
            stored.confirmed_data = document
            stored.confirmed_by = confirmed_by
            stored.confirmed_at = timezone.now()
            stored.status = self.STATUS.done
            stored.error_message = None
            stored.save(update_fields=["confirmed_data", "confirmed_by", "confirmed_at", "status", "error_message", "updated_at"])
        self.refresh_from_db()

    def __str__(self):
        return f"Transcript(user={self.user}, status={self.status})"


class TranscriptPage(models.Model):
    transcript = models.ForeignKey(
        Transcript,
        on_delete=models.CASCADE,
        related_name='pages'
    )
    file = models.FileField(upload_to='transcripts/pages/')
    page_number = models.PositiveIntegerField()

    def __str__(self):
        return f"Page {self.page_number} of Transcript({self.transcript_id})"
