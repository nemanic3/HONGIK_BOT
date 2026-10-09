"""Exercise historical migrations, not current model save hooks."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RequirementDataMigrationTests(TransactionTestCase):
    before = [("analysis", "0003_requirement_metadata")]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.before)
        self.old_apps = self.executor.loader.project_state(self.before).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_json_is_normalized_with_an_exact_original_snapshot(self):
        old_model = self.old_apps.get_model("analysis", "GraduationRequirement")
        original = ["과목", {"code": "001009", "name": "영어", "credit": "2.5", "aliases": ["English"], "extra": {"keep": True}}]
        old = old_model.objects.create(
            major="마이그레이션학과", year=2025, major_must_courses=original,
            general_must_courses=["글쓰기"], drbol_courses={"영역": ["영역과목"]},
            drbol_areas="영역", total_required=143, drbol_rules=None,
        )
        self.executor = MigrationExecutor(connection)
        targets = self.executor.loader.graph.leaf_nodes()
        self.executor.migrate(targets)
        new_model = self.executor.loader.project_state(targets).apps.get_model(
            "analysis", "GraduationRequirement"
        )
        migrated = new_model.objects.get(pk=old.pk)
        self.assertIsInstance(migrated.major_must_courses[0], dict)
        self.assertEqual(migrated.major_must_courses[0]["name"], "과목")
        self.assertEqual(migrated.major_must_courses[1]["code"], "001009")
        self.assertEqual(migrated.major_must_courses[1]["credit"], 2.5)
        self.assertEqual(migrated.major_must_courses[1]["extra"], {"keep": True})
        self.assertEqual(migrated.legacy_data["major_must_courses"], original)
        self.assertIsNone(migrated.legacy_data["major_selective_courses"])
        self.assertEqual(migrated.major_selective_courses, [])
        self.assertEqual(migrated.drbol_courses["영역"][0]["name"], "영역과목")
        self.assertIsNone(migrated.drbol_rules)
        self.assertEqual(migrated.total_required, 143)
        self.assertIsNone(migrated.verified_at)
        self.assertIsNone(migrated.source_reference)
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        restored = executor.loader.project_state(self.before).apps.get_model(
            "analysis", "GraduationRequirement"
        ).objects.get(pk=old.pk)
        self.assertEqual(restored.major_must_courses, original)
        self.assertIsNone(restored.legacy_data)
