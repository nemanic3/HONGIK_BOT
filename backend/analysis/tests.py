from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from transcripts.models import Transcript
from users.models import User

from .views import analyze_graduation

from .models import GraduationRequirement


class RequirementSchemaTests(TestCase):
    def test_drbol_rules_exists_in_migrated_database(self):
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(
                cursor, GraduationRequirement._meta.db_table
            )
        self.assertIn("drbol_rules", {column.name for column in columns})


class RequirementNormalizationTests(TestCase):
    def test_partial_course_save_does_not_overwrite_unrelated_stale_fields(self):
        requirement = GraduationRequirement.objects.create(
            major="테스트학과", year=2025, major_must_courses=["기존 전공"],
            general_must_courses=["기존 교양"], drbol_courses={"영역": ["기존 과목"]},
            drbol_rules=[{"area": "영역", "required_credit": 6}],
        )
        original_snapshot = requirement.legacy_data
        stale = GraduationRequirement.objects.get(pk=requirement.pk)
        current = GraduationRequirement.objects.get(pk=requirement.pk)
        current.general_must_courses = ["새 교양"]
        current.drbol_courses = {"영역": ["새 과목"]}
        current.drbol_rules = [{"area": "영역", "required_credit": 9}]
        current.save(update_fields=["general_must_courses", "drbol_courses", "drbol_rules"])
        current.refresh_from_db()

        stale.major_must_courses = ["새 전공"]
        stale.save(update_fields=["major_must_courses"])
        stale.refresh_from_db()

        self.assertEqual(stale.general_must_courses, current.general_must_courses)
        self.assertEqual(stale.drbol_courses, current.drbol_courses)
        self.assertEqual(stale.drbol_rules, current.drbol_rules)
        self.assertEqual(stale.major_must_courses[0]["name"], "새 전공")
        self.assertEqual(stale.legacy_data, original_snapshot)

    def test_partial_course_save_preserves_first_snapshot_without_saving_other_courses(self):
        requirement = GraduationRequirement.objects.create(
            major="테스트학과", year=2025, major_must_courses=[],
        )
        # Reproduce a legacy record that has not yet captured its original JSON.
        GraduationRequirement.objects.filter(pk=requirement.pk).update(
            legacy_data=None, general_must_courses=["원본 교양"],
        )
        requirement.refresh_from_db()
        requirement.major_must_courses = ["새 전공"]
        requirement.save(update_fields=["major_must_courses"])
        requirement.refresh_from_db()

        self.assertEqual(requirement.general_must_courses, ["원본 교양"])
        self.assertEqual(requirement.major_must_courses[0]["name"], "새 전공")
        self.assertEqual(requirement.legacy_data["major_must_courses"], ["새 전공"])
        self.assertEqual(requirement.legacy_data["general_must_courses"], ["원본 교양"])

    def test_mixed_course_references_are_normalized_without_losing_metadata(self):
        original = ["영어", {"code": "001009", "name": "영어", "aliases": ["English"], "note": "keep"}]
        requirement = GraduationRequirement.objects.create(
            major="테스트학과", year=2025, major_must_courses=original,
            general_must_courses=["글쓰기"], drbol_courses={"영역": ["과목"]},
            drbol_areas="영역", total_required=143,
        )
        requirement.refresh_from_db()
        self.assertIsInstance(requirement.major_must_courses[0], dict)
        self.assertEqual(requirement.major_must_courses[0]["name"], "영어")
        self.assertEqual(requirement.major_must_courses[1]["code"], "001009")
        self.assertEqual(requirement.major_must_courses[1]["note"], "keep")
        self.assertEqual(requirement.major_must_courses[1]["aliases"], ["English"])
        self.assertEqual(requirement.drbol_courses["영역"][0]["name"], "과목")
        self.assertEqual(requirement.major_selective_courses, [])
        self.assertEqual(requirement.total_required, 143)
        self.assertIsNone(requirement.drbol_rules)
        self.assertEqual(requirement.legacy_data["major_must_courses"], original)


class CohortSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="T300001", student_id="T300001", full_name="테스트",
            major="테스트학과", admission_year=2024, current_year=3,
        )
        self.course = {"name": "과목", "credit": 3, "grade": "A+", "semester": "1-1", "type": "전공"}
        Transcript.objects.create(user=self.user, parsed_data={"courses": [self.course]})
        self.req2025 = GraduationRequirement.objects.create(
            major=self.user.major, year=2025, major_must_courses=[],
            drbol_areas="", total_required=100,
        )
        self.req2024 = GraduationRequirement.objects.create(
            major=self.user.major, year=2024, major_must_courses=[],
            drbol_areas="", total_required=110,
        )

    def test_analysis_uses_the_exact_admission_year(self):
        result = analyze_graduation(self.user.id)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["data"]["total_required"], 110)

    def test_known_but_unsupported_cohort_never_falls_back_to_another_year(self):
        self.user.admission_year = 2026
        self.user.save()
        result = analyze_graduation(self.user.id)
        self.assertIn("error", result)

    def test_unknown_cohort_with_multiple_requirements_is_not_guessed(self):
        self.user.admission_year = None
        self.user.save()
        result = analyze_graduation(self.user.id)
        self.assertIn("error", result)

    def test_legacy_user_with_one_requirement_remains_compatible(self):
        self.user.admission_year = None
        self.user.major = "레거시학과"
        self.user.save()
        GraduationRequirement.objects.create(
            major=self.user.major, year=2025, major_must_courses=[],
            drbol_areas="", total_required=123,
        )
        self.assertEqual(analyze_graduation(self.user.id)["data"]["total_required"], 123)


class CourseSourceCompatibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="T400001", student_id="T400001", full_name="테스트",
            major="테스트학과", admission_year=2025,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        GraduationRequirement.objects.create(
            major=self.user.major, year=2025, major_must_courses=[], drbol_areas="영역",
        )
        self.course = {"code": "001009", "name": "영어", "credit": 3, "grade": "A+", "semester": "1-1", "type": "교양", "major_field": "교양필수"}

    def test_existing_apis_use_confirmed_courses_instead_of_legacy_values(self):
        transcript = Transcript.objects.create(
            user=self.user, status="done", parsed_data={"courses": [self.course]},
        )
        transcript.confirm_courses({"courses": [dict(self.course, credit=2.5)]}, confirmed_by=self.user)
        self.assertEqual(analyze_graduation(self.user.id)["data"]["total_completed"], 2.5)
        total = self.client.get(f"/api/analysis/credit/total/{self.user.id}/")
        self.assertEqual(total.status_code, 200)
        self.assertEqual(total.data["total_credit"], 2.5)
        general = self.client.get(f"/api/analysis/credit/general/{self.user.id}/")
        self.assertEqual(general.data["general_credit"], 2.5)
        semester = self.client.get(f"/api/semesters/courses/lists/{self.user.id}/")
        self.assertEqual(semester.data["1-1"][0]["credit"], 2.5)
        parsed = self.client.get(f"/api/transcripts/parsed/{self.user.id}/")
        self.assertEqual(parsed.data["courses"][0]["credit"], 2.5)

    def test_structured_ocr_document_works_without_the_legacy_buffer(self):
        Transcript.objects.create(user=self.user, status="done", ocr_data={"courses": [self.course]})
        result = analyze_graduation(self.user.id)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["data"]["total_completed"], 3)

    def test_raw_rows_are_unavailable_for_analysis_not_zero_credit(self):
        Transcript.objects.create(user=self.user, status="done", parsed_data=[["영어", "3"]])
        try:
            result = analyze_graduation(self.user.id)
        except (AttributeError, TypeError) as exc:
            self.fail(f"Raw OCR data reached the graduation calculator: {exc}")
        self.assertEqual(result["status"], 404)
        self.assertIn("error", result)

    def test_incomplete_draft_is_not_counted_as_a_completed_course(self):
        Transcript.objects.create(user=self.user, ocr_data={"courses": [{"name": "과목"}]})
        self.assertIsNone(Transcript.objects.get(user=self.user).get_analysis_document())
        self.assertIn("error", analyze_graduation(self.user.id))
