from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class DeploymentPrivacyTests(TestCase):
    @override_settings(DJANGO_REQUIRE_PROXY_SECRET=True, HONGIK_PROXY_SECRET='synthetic-test-secret', SECURE_SSL_REDIRECT=False)
    def test_direct_origin_is_denied_and_proxy_keeps_api_uncached(self):
        client = APIClient()
        self.assertEqual(client.get('/api/health/').status_code, 403)
        self.assertEqual(client.get('/api/health/', HTTP_X_HONGIK_PROXY_SECRET='wrong').status_code, 403)
        response = client.get('/api/health/', HTTP_X_HONGIK_PROXY_SECRET='synthetic-test-secret')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Cloudflare-CDN-Cache-Control'], 'no-store')
        self.assertNotIn('synthetic-test-secret', response.content.decode())

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_files_admin_and_anonymous_user_data_are_not_public(self):
        client = APIClient()
        for path in ['/media/transcripts/pages/synthetic.pdf', '/admin/', '/admin/login/']:
            response = client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertIn('no-store', response['Cache-Control'])
        response = client.get('/api/users/me/')
        self.assertEqual(response.status_code, 401)
        self.assertIn('no-store', response['Cache-Control'])
