import importlib.util
from pathlib import Path
import sqlite3
import tempfile
from django.test import SimpleTestCase

SPEC = importlib.util.spec_from_file_location('preservation_verifier', Path(__file__).resolve().parents[1] / 'scripts/verify_stage1_db.py')
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class PreservationVerifierTests(SimpleTestCase):
    def test_added_ruleset_metadata_is_allowed_but_original_rows_cannot_change(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after = [Path(directory) / name for name in ('before.sqlite3','after.sqlite3')]
            for path in (before, after):
                with sqlite3.connect(path) as db:
                    db.execute('CREATE TABLE django_content_type (id INTEGER PRIMARY KEY, app_label TEXT, model TEXT)')
                    db.execute('INSERT INTO django_content_type VALUES (1, ?, ?)', ('analysis','graduationrequirement'))
            with sqlite3.connect(after) as db:
                db.execute('INSERT INTO django_content_type VALUES (2, ?, ?)', ('analysis','requirementruleset'))
            self.assertTrue(verifier.verify(before, after)['passed'])
            with sqlite3.connect(after) as db:
                db.execute('UPDATE django_content_type SET model=? WHERE id=1', ('changed',))
            with self.assertRaises(AssertionError):
                verifier.verify(before, after)
