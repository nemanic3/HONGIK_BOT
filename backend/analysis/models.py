from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import models

from common.course_schema import (
    REQUIREMENT_COURSE_FIELDS,
    CourseSchemaError,
    normalize_area_courses,
    normalize_course_references,
)

class GraduationRequirement(models.Model):
    major = models.CharField(max_length=100)        # 학과명
    year = models.PositiveSmallIntegerField()       # 입학년도 (기존 year 이름은 호환성 유지)

    # 총 학점 요건
    total_required = models.IntegerField(default=132)
    major_required = models.IntegerField(default=50)
    general_required = models.IntegerField(default=8)
    drbol_required = models.IntegerField(default=18)
    special_general_required = models.IntegerField(default=3)
    sw_required = models.IntegerField(default=9)
    msc_required = models.IntegerField(default=23)

    # 전공 필수 / 전공 선택
    # 각 아이템 예시: {"code":"101510","name":"컴퓨터구조","semester":"3-1","aliases":["컴구"]}
    major_must_courses = models.JSONField(
        help_text="전공필수 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}"
    )
    major_selective_courses = models.JSONField(
        help_text="전공선택 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}",
        null=True, blank=True
    )

    # 교양 필수 / 교양 선택 / 특성화교양 / SW / MSC
    # 각 리스트의 항목 포맷은 동일: {code, name, semester?, aliases?}
    general_must_courses = models.JSONField(
        help_text="교양필수 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}",
        null=True, blank=True
    )
    general_selective_courses = models.JSONField(
        help_text="일반선택(교양선택) 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}",
        null=True, blank=True
    )
    special_general_courses = models.JSONField(
        help_text="특성화교양 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}",
        null=True, blank=True
    )
    sw_courses = models.JSONField(
        help_text="SW/데이터활용역량 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}",
        null=True, blank=True
    )
    msc_courses = models.JSONField(
        help_text="MSC 과목 리스트(JSON). 각 항목: {code, name, semester?, aliases?}",
        null=True, blank=True
    )

    # 드볼 (레거시 + 신규 규칙)
    drbol_areas = models.TextField(
        help_text="(레거시) 드볼 영역 이름(콤마 구분). 예: '인문과예술,사회와문화,자연과기술'",
        blank=True  # Keep the existing non-null SQLite column; use "" for no areas.
    )
    # 새 규칙: 영역별 요구학점 명시
    # 예: [{"area":"인문과예술","required_credit":6},{"area":"사회와문화","required_credit":6},{"area":"자연과기술","required_credit":6}]
    drbol_rules = models.JSONField(
        help_text="드볼 영역 규칙(JSON). 각 항목: {area, required_credit}",
        null=True, blank=True
    )
    # 영역별 실제 과목(선택): { "인문과예술": [{code,name,...}], "사회와문화": [...] }
    drbol_courses = models.JSONField(
        help_text="드볼 영역별 과목 리스트(JSON). 키=area, 값=과목 배열(각 항목: {code, name, semester?, aliases?})",
        null=True, blank=True
    )

    # Original JSON is retained before normalization; policy verification is explicit.
    legacy_data = models.JSONField(null=True, blank=True, editable=False)
    source_reference = models.TextField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('major', 'year')

    def normalize_course_data(self):
        fields = (*REQUIREMENT_COURSE_FIELDS, "drbol_courses", "drbol_rules")
        original = {field: deepcopy(getattr(self, field)) for field in fields}
        try:
            normalized = {
                field: normalize_course_references(getattr(self, field))
                for field in REQUIREMENT_COURSE_FIELDS
            }
            normalized["drbol_courses"] = normalize_area_courses(self.drbol_courses)
        except CourseSchemaError as exc:
            raise ValidationError(str(exc)) from exc
        if self.legacy_data is None:
            self.legacy_data = original
        for field, value in normalized.items():
            setattr(self, field, value)

    def clean(self):
        super().clean()
        self.normalize_course_data()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        course_fields = {*REQUIREMENT_COURSE_FIELDS, "drbol_courses", "drbol_rules"}
        if update_fields is None or course_fields.intersection(update_fields):
            self.normalize_course_data()
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"legacy_data"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.major} {self.year}학번 졸업 요건"


class RequirementRuleSet(models.Model):
    """Versioned, explicit program rules; legacy rows are not overwritten."""
    major = models.CharField(max_length=100)
    campus = models.CharField(max_length=20, default="서울")
    admission_year_from = models.PositiveSmallIntegerField()
    admission_year_to = models.PositiveSmallIntegerField()
    curriculum_year = models.PositiveSmallIntegerField()
    accreditation_track = models.CharField(max_length=20, choices=[
        ("accredited", "공학교육 인증"), ("non_accredited", "비인증"),
    ])
    version = models.CharField(max_length=80)
    data = models.JSONField()
    source_document = models.TextField()
    source_sha256 = models.CharField(max_length=64)
    source_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["major", "campus", "admission_year_from", "admission_year_to", "accreditation_track", "version"],
            name="unique_requirement_ruleset_version",
        )]

    def clean(self):
        super().clean()
        from .policy import validate_policy_data
        if self.admission_year_from > self.admission_year_to:
            raise ValidationError("입학연도 범위가 역전되었습니다.")
        if self.accreditation_track not in {"accredited", "non_accredited"}:
            raise ValidationError("인증과정을 명시해야 합니다.")
        validate_policy_data(self.data)
        if self.pk is not None:
            fields = [field.attname for field in self._meta.concrete_fields if field.name not in {'id', 'created_at'}]
            original = type(self).objects.using(self._state.db or 'default').filter(pk=self.pk).values(*fields).first()
            if original and any(getattr(self, field) != original[field] for field in fields):
                raise ValidationError('Existing rule versions are immutable; create a new row with a new version.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
