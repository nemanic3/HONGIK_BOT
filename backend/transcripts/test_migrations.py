from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TranscriptDataMigrationTests(TransactionTestCase):
    # Keep the historical user model and its actual test-DB table in sync when
    # newer user migrations are present; migrate only the isolated test database.
    before = [("transcripts", "0003_separate_course_data"), ("users", "0002_admission_year")]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.before)
        self.old_apps = self.executor.loader.project_state(self.before).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_payloads_are_preserved_without_becoming_user_confirmations(self):
        user_model = self.old_apps.get_model("users", "User")
        transcript_model = self.old_apps.get_model("transcripts", "Transcript")
        user = user_model.objects.create(username="T100010", student_id="T100010", full_name="테스트")
        payload = {"courses": [{"name": "영어", "code": "001009", "credit": "3", "grade": "A+"}], "metadata": "keep"}
        structured = transcript_model.objects.create(user_id=user.id, status="completed", parsed_data=payload)
        rows = [["001009", "영어", "3"]]
        raw = transcript_model.objects.create(user_id=user.id, status="done", parsed_data=rows)
        pending = transcript_model.objects.create(user_id=user.id, status="pending", parsed_data=None)
        self.executor = MigrationExecutor(connection)
        targets = self.executor.loader.graph.leaf_nodes()
        self.executor.migrate(targets)
        model = self.executor.loader.project_state(targets).apps.get_model("transcripts", "Transcript")
        self.assertEqual(model.objects.count(), 3)
        migrated = model.objects.get(pk=structured.pk)
        self.assertEqual(migrated.status, "done")
        self.assertEqual(migrated.legacy_status, "completed")
        self.assertEqual(migrated.parsed_data, payload)
        self.assertEqual(migrated.ocr_raw_data, payload)
        self.assertEqual(migrated.ocr_data["schema_version"], 1)
        self.assertEqual(migrated.ocr_data["courses"][0]["credit"], 3)
        self.assertIsNone(migrated.ocr_data["courses"][0]["semester"])
        self.assertIsNone(migrated.confirmed_data)
        self.assertIsNone(migrated.confirmed_at)
        self.assertIsNone(migrated.confirmed_by_id)
        migrated_raw = model.objects.get(pk=raw.pk)
        self.assertEqual(migrated_raw.ocr_raw_data, rows)
        self.assertEqual(migrated_raw.parsed_data, rows)
        self.assertIsNone(migrated_raw.ocr_data)
        self.assertIsNone(model.objects.get(pk=pending.pk).ocr_data)
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        restored = executor.loader.project_state(self.before).apps.get_model("transcripts", "Transcript")
        self.assertEqual(restored.objects.get(pk=structured.pk).status, "completed")
        self.assertEqual(restored.objects.get(pk=structured.pk).parsed_data, payload)
        self.assertEqual(restored.objects.get(pk=raw.pk).parsed_data, rows)
