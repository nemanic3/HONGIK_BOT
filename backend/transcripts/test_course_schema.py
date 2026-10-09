from django.test import SimpleTestCase

from common import course_schema


class CourseSchemaTests(SimpleTestCase):
    def test_numeric_credit_is_normalized_without_rewriting_identifiers(self):
        original = {"code": "001009", "name": " 영어 ", "credit": "2.5", "source": {"page": 1}}
        result = course_schema.normalize_course_reference(original)
        self.assertEqual(result["credit"], 2.5)
        self.assertEqual(result["code"], "001009")
        self.assertEqual(result["name"], " 영어 ")
        self.assertEqual(result["source"], {"page": 1})
        self.assertEqual(original["credit"], "2.5")

    def test_invalid_credit_is_rejected_instead_of_becoming_zero(self):
        for credit in (True, -1, "unknown", "NaN", "Infinity", "1e1000", "1e-1000", {}, []):
            with self.subTest(credit=credit), self.assertRaises(course_schema.CourseSchemaError):
                course_schema.normalize_course_reference({"name": "과목", "credit": credit})

    def normalize_document(self, value, **kwargs):
        normalize = getattr(course_schema, "normalize_course_document", None)
        self.assertTrue(callable(normalize), "The shared document schema is not implemented")
        return normalize(value, **kwargs)

    def test_legacy_course_objects_become_a_versioned_document(self):
        source = {"courses": [{"code": "001009", "name": "영어", "credit": "3", "grade": "A+"}], "source": "legacy"}
        document = self.normalize_document(source)
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["courses"][0]["credit"], 3)
        self.assertIsNone(document["courses"][0]["semester"])
        self.assertFalse(document["courses"][0]["retake"])
        self.assertEqual(document["source"], "legacy")
        self.assertNotIn("schema_version", source)
        self.assertEqual(self.normalize_document(source["courses"])["courses"], document["courses"])

    def test_ocr_rows_are_not_guessed_into_courses(self):
        normalize = getattr(course_schema, "normalize_course_document", None)
        self.assertTrue(callable(normalize))
        for value in ([["101510", "컴퓨터구조", "3"]], "raw OCR text", ["영어"], {"schema_version": 2, "courses": []}):
            with self.subTest(value=value), self.assertRaises(course_schema.CourseSchemaError):
                normalize(value)

    def test_confirmation_requires_explicit_course_details(self):
        normalize = getattr(course_schema, "normalize_course_document", None)
        self.assertTrue(callable(normalize))
        with self.assertRaises(course_schema.CourseSchemaError):
            normalize({"courses": [{"name": "과목"}]}, for_confirmation=True)
        course = {"name": "과목", "credit": "2.5", "grade": "A+", "semester": "2025-1", "type": "전공"}
        result = normalize({"courses": [course]}, for_confirmation=True)
        self.assertEqual(result["courses"][0]["credit"], 2.5)
        with self.assertRaises(course_schema.CourseSchemaError):
            normalize({"courses": [dict(course, retake="false")]})
