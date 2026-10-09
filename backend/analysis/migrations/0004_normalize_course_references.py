"""Normalize JSON shape only; preserve all original values and policy numbers."""

from copy import deepcopy

from django.db import migrations

from common.migration_schema_v1 import (
    REQUIREMENT_COURSE_FIELDS,
    normalize_area_courses,
    normalize_course_references,
)

SNAPSHOT_FIELDS = (*REQUIREMENT_COURSE_FIELDS, "drbol_courses", "drbol_rules")


def normalized_values(snapshot):
    result = {
        field: normalize_course_references(snapshot[field])
        for field in REQUIREMENT_COURSE_FIELDS
    }
    result["drbol_courses"] = normalize_area_courses(snapshot["drbol_courses"])
    return result


def forwards(apps, schema_editor):
    model = apps.get_model("analysis", "GraduationRequirement")
    alias = schema_editor.connection.alias
    for row in model.objects.using(alias).all().iterator():
        if row.legacy_data is not None:
            continue
        snapshot = {field: deepcopy(getattr(row, field)) for field in SNAPSHOT_FIELDS}
        normalized = normalized_values(snapshot)
        model.objects.using(alias).filter(pk=row.pk).update(
            **normalized, legacy_data=snapshot
        )


def backwards(apps, schema_editor):
    model = apps.get_model("analysis", "GraduationRequirement")
    alias = schema_editor.connection.alias
    for row in model.objects.using(alias).exclude(legacy_data=None).iterator():
        snapshot = row.legacy_data
        expected = normalized_values(snapshot)
        if any(getattr(row, field) != value for field, value in expected.items()):
            raise RuntimeError("Requirement data changed after migration; refusing a lossy rollback.")
        if row.drbol_rules != snapshot["drbol_rules"]:
            raise RuntimeError("Area rules changed after migration; refusing a lossy rollback.")
        model.objects.using(alias).filter(pk=row.pk).update(
            **snapshot, legacy_data=None
        )


class Migration(migrations.Migration):
    dependencies = [("analysis", "0003_requirement_metadata")]
    operations = [migrations.RunPython(forwards, backwards)]
