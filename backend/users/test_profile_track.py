from django.test import TestCase
from rest_framework.test import APIClient
from users.models import User


class ProfileTrackTests(TestCase):
    def test_me_without_optional_student_id_returns_profile_and_track(self):
        user = User.objects.create(username='T600001', student_id='T600001', full_name='테스트', admission_year=2025)
        client = APIClient()
        client.force_authenticate(user)
        result = client.get('/api/users/me/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['id'], user.id)
        self.assertEqual(result.data['admission_year'], 2025)
        self.assertEqual(result.data['accreditation_track'], '')

    def test_profile_track_is_explicit_and_validation_rejects_unknown_values(self):
        from users.serializers import UserSerializer
        user = User.objects.create(username='T600002', student_id='T600002', full_name='테스트')
        serializer = UserSerializer(user, data={'accreditation_track':'non_accredited'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(User.objects.get(pk=user.pk).accreditation_track, 'non_accredited')
        bad = UserSerializer(user, data={'accreditation_track':'automatic'}, partial=True)
        self.assertFalse(bad.is_valid())
