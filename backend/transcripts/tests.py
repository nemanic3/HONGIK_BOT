from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User

from .models import Transcript


class TranscriptDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="T100001", student_id="T100001", full_name="테스트",
            major="테스트학과", current_year=1,
        )
        self.course = {
            "code": "001009", "name": "영어", "credit": 3,
            "grade": "A+", "semester": "1-1", "type": "교양", "major_field": "교양필수",
        }

    def require_data_fields(self):
        fields = {field.name for field in Transcript._meta.fields}
        self.assertTrue({"ocr_raw_data", "ocr_data", "confirmed_data", "confirmed_at", "confirmed_by"}.issubset(fields))

    def test_identical_raw_retry_preserves_structured_courses(self):
        transcript = Transcript.objects.create(user=self.user)
        raw = [["001009", "영어", "3"]]
        transcript.record_ocr_result(raw, courses={"courses": [self.course]})
        expected = deepcopy(transcript.ocr_data)
        transcript.record_ocr_result(raw)
        self.assertEqual(transcript.ocr_data, expected)
        self.assertIsNotNone(transcript.get_analysis_document())

    def test_confirmed_results_are_available_independently_of_ocr_status(self):
        client = APIClient()
        client.force_authenticate(self.user)
        for state in ("pending", "processing", "error"):
            for courses in ([], [self.course]):
                with self.subTest(state=state, courses=courses):
                    transcript = Transcript.objects.create(user=self.user, status=state)
                    transcript.confirm_courses({"courses": courses}, confirmed_by=self.user)
                    response = client.get(f"/api/transcripts/parsed/{self.user.id}/")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(len(response.data["courses"]), len(courses))

    def test_raw_ocr_and_confirmed_data_are_separate(self):
        self.require_data_fields()
        original = {"courses": [deepcopy(self.course)], "source": "legacy"}
        transcript = Transcript.objects.create(user=self.user, parsed_data=original)
        transcript.record_ocr_result(original)
        transcript.confirm_courses({"courses": [dict(self.course, credit=2.5)]}, confirmed_by=self.user)
        transcript.refresh_from_db()
        self.assertEqual(transcript.ocr_raw_data, original)
        self.assertEqual(transcript.parsed_data, original)
        self.assertEqual(transcript.ocr_data["courses"][0]["credit"], 3)
        self.assertEqual(transcript.confirmed_data["courses"][0]["credit"], 2.5)
        self.assertEqual(transcript.get_course_document()["courses"][0]["credit"], 2.5)
        self.assertEqual(transcript.confirmed_by_id, self.user.id)
        self.assertIsNotNone(transcript.confirmed_at)

    def test_raw_rows_are_preserved_without_creating_guessed_courses(self):
        self.require_data_fields()
        transcript = Transcript.objects.create(user=self.user)
        raw = [["101510", "컴퓨터구조", "3"]]
        transcript.record_ocr_result(raw)
        transcript.refresh_from_db()
        self.assertEqual(transcript.ocr_raw_data, raw)
        self.assertIsNone(transcript.ocr_data)
        self.assertIsNone(transcript.confirmed_data)
        self.assertIsNone(transcript.get_course_document())

    def test_other_user_cannot_confirm_a_transcript(self):
        self.require_data_fields()
        other = User.objects.create(username="T100002", student_id="T100002", full_name="다른이")
        transcript = Transcript.objects.create(user=self.user)
        with self.assertRaises(ValidationError):
            transcript.confirm_courses({"courses": [self.course]}, confirmed_by=other)
        transcript.refresh_from_db()
        self.assertIsNone(transcript.confirmed_data)

    def test_empty_confirmed_document_does_not_fall_back_to_ocr(self):
        self.require_data_fields()
        transcript = Transcript.objects.create(user=self.user)
        transcript.record_ocr_result({"courses": [self.course]})
        transcript.confirm_courses({"courses": []}, confirmed_by=self.user)
        self.assertEqual(transcript.get_course_document()["courses"], [])
