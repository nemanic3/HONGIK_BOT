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


# Course history is additive. Transcript JSON remains the original student record.
import uuid
from django.core.validators import MinValueValidator, RegexValidator


class CourseIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)


class CourseEvidence(models.Model):
    def __str__(self):
        return f'{self.document} p.{self.pdf_page}'

    document = models.TextField()
    sha256 = models.CharField(max_length=64, validators=[RegexValidator(r'^[0-9a-f]{64}$')])
    pdf_page = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    printed_page = models.CharField(max_length=40)
    statement = models.TextField(help_text='Exact applicable statement, not an inferred code mapping')
    official_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.CharField(max_length=120, blank=True)

    def clean(self):
        if self.official_verified and (not self.verified_at or not self.verified_by.strip()):
            raise ValidationError('Official verification requires reviewer and time.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CourseVersion(models.Model):
    """One exact calendar term. No extrapolation into unrecorded years/terms."""
    course = models.ForeignKey(CourseIdentity, on_delete=models.PROTECT, related_name='versions')
    campus = models.CharField(max_length=20, default='서울')
    major = models.CharField(max_length=100, default='컴퓨터공학과')
    academic_year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])
    term = models.CharField(max_length=10, choices=[('1','1'),('2','2'),('summer','summer'),('winter','winter')])
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=200)
    credit = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    classification = models.CharField(max_length=80, blank=True)
    evidence = models.ForeignKey(CourseEvidence, on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.academic_year}-{self.term} {self.code} {self.name}'

    class Meta:
        constraints = [models.UniqueConstraint(fields=['course','campus','major','academic_year','term'], name='course_exact_term_version')]
        indexes = [models.Index(fields=['campus','major','code','academic_year','term'], name='course_code_term_lookup')]

    def clean(self):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values().first()
            if original and any(original[f.attname] != getattr(self, f.attname) for f in self._meta.concrete_fields):
                raise ValidationError('Published course versions are immutable.')
        # Sharing an identity itself asserts sameness, so changes require explicit
        # verified relations between separate identities instead of silent reuse.
        if self.course_id:
            others = type(self).objects.filter(course_id=self.course_id).exclude(pk=self.pk)
            if any(any(getattr(v,k) != getattr(self,k) for k in ('code','name','credit','classification','campus','major')) for v in others):
                raise ValidationError('Changed attributes require a separate identity and evidenced same_course relation.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CourseRelation(models.Model):
    # Direction: an attended source version can satisfy the target requirement.
    source = models.ForeignKey(CourseVersion, on_delete=models.PROTECT, related_name='outgoing_relations')
    target = models.ForeignKey(CourseVersion, on_delete=models.PROTECT, related_name='incoming_relations')
    kind = models.CharField(max_length=20, choices=[('same_course','동일과목'),('replacement','대체과목'),('retake','재수강 허용')])
    evidence = models.ForeignKey(CourseEvidence, on_delete=models.PROTECT)
    policy_version = models.CharField(max_length=80, blank=True)
    criterion_id = models.CharField(max_length=80, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','target','kind','policy_version','criterion_id'], name='unique_course_relation_scope')]

    def clean(self):
        if self.source_id and self.target_id:
            if self.source_id == self.target_id:
                raise ValidationError('Relation endpoints must differ.')
            if (self.source.campus, self.source.major) != (self.target.campus, self.target.major):
                raise ValidationError('Cross-program equivalence requires a separate policy.')
            if self.kind != 'same_course' and self.source.course_id == self.target.course_id:
                raise ValidationError('Replacement/retake must not imply shared identity.')
        if self.kind == 'replacement' and (not self.policy_version or not self.criterion_id):
            raise ValidationError('Replacement requires exact policy version and criterion.')
        if self.kind != 'replacement' and (self.policy_version or self.criterion_id):
            raise ValidationError('Only replacement relations carry requirement scope.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
