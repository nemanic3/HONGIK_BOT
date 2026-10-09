"""Archive legacy payloads without pretending a user reviewed them."""

from copy import deepcopy

from django.db import migrations

from common.migration_schema_v1 import CourseSchemaError, normalize_course_document


def structured(value):
    try:
        return normalize_course_document(value)
    except CourseSchemaError:
        return None


def forwards(apps, schema_editor):
    model = apps.get_model("transcripts", "Transcript")
    alias = schema_editor.connection.alias
    for row in model.objects.using(alias).all().iterator():
        if row.legacy_status is not None:
            continue
        updates = {"legacy_status": row.status}
        raw = row.ocr_raw_data if row.ocr_raw_data is not None else row.parsed_data
        if row.ocr_raw_data is None:
            updates["ocr_raw_data"] = deepcopy(raw)
        if row.ocr_data is None:
            updates["ocr_data"] = structured(raw)
        if row.status == "completed":
            updates["status"] = "done"
        model.objects.using(alias).filter(pk=row.pk).update(**updates)


def backwards(apps, schema_editor):
    model = apps.get_model("transcripts", "Transcript")
    alias = schema_editor.connection.alias
    for row in model.objects.using(alias).exclude(legacy_status=None).iterator():
        expected_status = "done" if row.legacy_status == "completed" else row.legacy_status
        if (
            row.confirmed_data is not None or row.confirmed_at is not None
            or row.confirmed_by_id is not None or row.status != expected_status
            or row.ocr_raw_data != row.parsed_data
            or row.ocr_data != structured(row.parsed_data)
        ):
            raise RuntimeError("Transcript data changed after migration; refusing a lossy rollback.")
        model.objects.using(alias).filter(pk=row.pk).update(
            status=row.legacy_status, legacy_status=None, ocr_data=None, ocr_raw_data=None
        )


class Migration(migrations.Migration):
    dependencies = [("transcripts", "0003_separate_course_data")]
    operations = [migrations.RunPython(forwards, backwards)]
