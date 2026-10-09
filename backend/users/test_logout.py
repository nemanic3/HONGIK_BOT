from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class LogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='T881001', student_id='T881001', password='synthetic-test-only')
        self.other = User.objects.create_user(username='T881002', student_id='T881002', password='synthetic-test-only')
        self.refresh = RefreshToken.for_user(self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(self.refresh.access_token))

    def test_logout_revokes_refresh_token(self):
        response = self.client.post('/api/users/logout/', {'refresh': str(self.refresh)}, format='json')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/api/users/refresh/', {'refresh': str(self.refresh)}, format='json')
        self.assertEqual(response.status_code, 401)

    def test_logout_cannot_revoke_another_users_token(self):
        other = str(RefreshToken.for_user(self.other))
        response = self.client.post('/api/users/logout/', {'refresh': other}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/users/refresh/', {'refresh': other}, format='json')
        self.assertEqual(response.status_code, 200)
