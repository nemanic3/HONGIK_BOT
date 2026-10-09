"""Verify stage-1 migration preservation against an SQLite backup (read-only).

Usage: python scripts/verify_stage1_db.py BEFORE.sqlite3 AFTER.sqlite3
Never prints user rows, credentials, or transcript contents.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.migration_schema_v1 import (  # noqa: E402
    REQUIREMENT_COURSE_FIELDS,
    CourseSchemaError,
    normalize_area_courses,
    normalize_course_document,
    normalize_course_references,
)


def read_tables(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    tables = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if name.startswith("sqlite_"):
            continue
        quoted = '"' + name.replace('"', '""') + '"'
        primary_key = [row[1] for row in connection.execute(f"PRAGMA table_info({quoted})") if row[5]]
        ordering = ", ".join('"' + key.replace('"', '""') + '"' for key in primary_key)
        query = f"SELECT * FROM {quoted}" + (f" ORDER BY {ordering}" if ordering else "")
        tables[name] = [dict(row) for row in connection.execute(query)]
    connection.close()
    return tables


def decoded(value):
    return json.loads(value) if value is not None else None


def verify(before_path, after_path):
    before, after = read_tables(before_path), read_tables(after_path)
    assert set(before) <= set(after), "A table disappeared"
    counts = {}
    references = (*REQUIREMENT_COURSE_FIELDS, "drbol_courses")
    for table, rows in before.items():
        counts[table] = len(rows)
        if table == "django_migrations":
            assert all(row in after[table] for row in rows), "Migration history lost"
            continue
        if table in {"django_content_type", "auth_permission"}:
            assert all(row in after[table] for row in rows), f"Original metadata changed: {table}"
            extra = [row for row in after[table] if row not in rows]
            if table == "django_content_type":
                assert all(row["app_label"] == "analysis" and row["model"] == "requirementruleset" for row in extra)
            else:
                new_type_ids = {row["id"] for row in after.get("django_content_type", [])
                                if row["app_label"] == "analysis" and row["model"] == "requirementruleset"}
                assert all(row["content_type_id"] in new_type_ids and row["codename"] in
                           {"add_requirementruleset", "change_requirementruleset", "delete_requirementruleset", "view_requirementruleset"}
                           for row in extra), "Unexpected added permissions"
            continue
        assert len(rows) == len(after[table]), f"Row count changed: {table}"
        for old, new in zip(rows, after[table]):
            if "id" in old:
                assert old["id"] == new["id"], f"Identity changed: {table}"
            for field, value in old.items():
                if table == "analysis_graduationrequirement" and field in references:
                    assert decoded(new["legacy_data"])[field] == decoded(value)
                    normalize = normalize_area_courses if field == "drbol_courses" else normalize_course_references
                    assert decoded(new[field]) == normalize(decoded(value))
                elif table == "transcripts_transcript" and field == "status":
                    assert new[field] == ("done" if value == "completed" else value)
                    assert new["legacy_status"] == value
                else:
                    assert new[field] == value, f"Original value changed: {table}.{field}"
            if table == "transcripts_transcript":
                raw = decoded(old["parsed_data"])
                assert decoded(new["ocr_raw_data"]) == raw
                try:
                    expected = normalize_course_document(raw)
                except CourseSchemaError:
                    expected = None
                assert decoded(new["ocr_data"]) == expected
                assert all(new[field] is None for field in ("confirmed_data", "confirmed_at", "confirmed_by_id"))
            elif table == "users_user":
                assert new["admission_year"] is None
            elif table == "analysis_graduationrequirement":
                assert all(new[field] is None for field in ("drbol_rules", "source_reference", "verified_at"))
    return {"passed": True, "integrity_check": "ok", "foreign_key_check": "ok", "original_row_counts": counts}


if __name__ == "__main__":
    print(json.dumps(verify(*sys.argv[1:]), ensure_ascii=False, indent=2))
