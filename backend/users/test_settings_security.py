"""Settings checks use isolated processes and no user database."""
import os
import subprocess
import sys
from django.test import SimpleTestCase


class SettingsSecurityTests(SimpleTestCase):
    def run_settings(self, **values):
        env = dict(os.environ)
        env.pop('DJANGO_SECRET_KEY', None)
        env.update(values)
        return subprocess.run([sys.executable, '-B', '-c',
            'import core.settings as s; print(s.DEBUG); print(bool(s.SECRET_KEY))'],
            env=env, capture_output=True, text=True)

    def test_production_requires_explicit_secret(self):
        result = self.run_settings(DJANGO_DEBUG='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', result.stderr)

    def test_development_uses_nonliteral_secret_and_production_accepts_environment(self):
        dev = self.run_settings(DJANGO_DEBUG='1')
        self.assertEqual(dev.returncode, 0, dev.stderr)
        prod = self.run_settings(DJANGO_DEBUG='0', DJANGO_SECRET_KEY='synthetic-settings-test-only-not-a-real-credential')
        self.assertEqual(prod.returncode, 0, prod.stderr)
        self.assertEqual(prod.stdout.splitlines(), ['False', 'True'])
