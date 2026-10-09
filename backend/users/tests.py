from django.test import TestCase

from .models import User
from .serializers import SignupSerializer, UserSerializer


class AdmissionYearTests(TestCase):
    def payload(self, **extra):
        return {
            "student_id": "T200001", "full_name": "테스트", "current_year": 3,
            "major": "테스트학과", "password": "test-only-password-123", **extra,
        }

    def test_admission_year_is_stored_independently_of_current_year(self):
        serializer = SignupSerializer(data=self.payload(admission_year=2025))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(getattr(user, "admission_year", None), 2025)
        self.assertEqual(user.current_year, 3)
        self.assertEqual(UserSerializer(user).data["admission_year"], 2025)

    def test_old_signup_payload_does_not_guess_admission_year(self):
        serializer = SignupSerializer(data=self.payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertIn("admission_year", {field.name for field in User._meta.fields})
        self.assertIsNone(user.admission_year)
        self.assertEqual(user.current_year, 3)

    def test_invalid_admission_year_is_rejected(self):
        for year in (0, 999, 10000, "not-a-year"):
            with self.subTest(year=year):
                serializer = SignupSerializer(data=self.payload(admission_year=year))
                self.assertFalse(serializer.is_valid())
                self.assertIn("admission_year", serializer.errors)
