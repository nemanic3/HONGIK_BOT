import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase


class ProcessingSettingsTests(SimpleTestCase):
    def test_inline_is_an_explicit_environment_setting_and_default_is_celery(self):
        for configured, expected in [('inline', 'inline'), (None, 'celery')]:
            env = dict(os.environ)
            env.pop('TRANSCRIPT_PROCESSING', None)
            if configured:
                env['TRANSCRIPT_PROCESSING'] = configured
            result = subprocess.run([sys.executable, '-c',
                "from core import settings; print(settings.TRANSCRIPT_PROCESSING)"],
                cwd=Path(__file__).resolve().parent.parent, env=env,
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), expected)
